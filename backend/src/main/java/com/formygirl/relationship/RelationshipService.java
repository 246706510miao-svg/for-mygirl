package com.formygirl.relationship;

import com.formygirl.common.ApiException;
import com.formygirl.identity.CurrentPerson;
import com.formygirl.identity.IdentityRepository;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

@Service
public class RelationshipService {
    public static final String VIEW_USER = "USER";
    public static final String VIEW_BOUND_ADMIN = "BOUND_ADMIN";
    public static final String VIEW_OPS_ADMIN = "OPS_ADMIN";

    private final RelationshipRepository relationshipRepository;
    private final IdentityRepository identityRepository;

    public RelationshipService(RelationshipRepository relationshipRepository, IdentityRepository identityRepository) {
        this.relationshipRepository = relationshipRepository;
        this.identityRepository = identityRepository;
    }

    // 这个函数组装当前登录人的视角上下文。
    public Map<String, Object> viewContext(CurrentPerson person) {
        String currentViewRole = currentViewRole(person);
        Map<String, Object> binding = binding(person);
        Map<String, Object> viewOwner = personDto(person.id(), person.displayName(), person.role());
        if (VIEW_BOUND_ADMIN.equals(currentViewRole)) {
            Object boundUser = binding.get("boundUser");
            if (boundUser instanceof Map<?, ?> map) {
                viewOwner = castMap(map);
            }
        }
        return dto(
                "person", personDto(person.id(), person.displayName(), person.role()),
                "currentViewRole", currentViewRole,
                "viewOwner", viewOwner,
                "binding", binding
        );
    }

    // 这个函数切换普通用户的手机端视角。
    public Map<String, Object> switchViewRole(CurrentPerson person, String requestedViewRole) {
        if (person.isOpsAdmin()) {
            throw new ApiException(HttpStatus.FORBIDDEN, "FORBIDDEN", "后台人员不使用手机端绑定视角");
        }
        String normalized = normalizeViewRole(requestedViewRole);
        if (VIEW_BOUND_ADMIN.equals(normalized)) {
            requireBoundTarget(person);
        }
        identityRepository.updateCurrentViewRole(person.id(), normalized);
        return viewContext(person);
    }

    // 这个函数读取当前用户绑定信息。
    public Map<String, Object> binding(CurrentPerson person) {
        if (person.isOpsAdmin()) {
            return dto("active", false, "boundUser", null, "permissions", List.of(), "incomingInvitations", List.of(), "outgoingInvitations", List.of());
        }
        Map<String, Object> binding = relationshipRepository.activeBinding(person.id());
        if (binding.isEmpty()) {
            return dto(
                    "active", false,
                    "boundUser", null,
                    "permissions", List.of(),
                    "incomingInvitations", relationshipRepository.incomingInvitations(person.id()).stream().map(row -> invitationDto(row, true)).toList(),
                    "outgoingInvitations", relationshipRepository.outgoingInvitations(person.id()).stream().map(row -> invitationDto(row, false)).toList()
            );
        }
        String bindingId = String.valueOf(binding.get("id"));
        String targetUserId = String.valueOf(binding.get("target_user_id"));
        return dto(
                "active", true,
                "bindingId", bindingId,
                "boundUser", personDto(targetUserId, String.valueOf(binding.get("target_display_name")), String.valueOf(binding.get("target_role")), binding.get("target_login_name")),
                "permissions", relationshipRepository.permissions(bindingId, person.id()),
                "incomingInvitations", relationshipRepository.incomingInvitations(person.id()).stream().map(row -> invitationDto(row, true)).toList(),
                "outgoingInvitations", relationshipRepository.outgoingInvitations(person.id()).stream().map(row -> invitationDto(row, false)).toList()
        );
    }

    // 这个函数向另一个真实账号发起绑定邀请。
    public Map<String, Object> invite(CurrentPerson person, String targetLoginName) {
        if (person.isOpsAdmin()) {
            throw new ApiException(HttpStatus.FORBIDDEN, "FORBIDDEN", "后台人员不能发起用户绑定");
        }
        String loginName = normalizeLoginName(targetLoginName);
        Map<String, Object> target = identityRepository.accountByLoginName(loginName);
        if (target.isEmpty() || !"USER".equals(String.valueOf(target.get("role"))) || !boolValue(target.get("enabled")) || !boolValue(target.get("person_enabled"))) {
            throw new ApiException(HttpStatus.NOT_FOUND, "BINDING_TARGET_NOT_FOUND", "没有找到可绑定的普通用户");
        }
        String targetUserId = String.valueOf(target.get("person_id"));
        if (person.id().equals(targetUserId)) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "BINDING_SELF_NOT_ALLOWED", "不能绑定自己");
        }
        Map<String, Object> existingPair = relationshipRepository.bindingPair(person.id(), targetUserId);
        if ("active".equals(String.valueOf(existingPair.get("status")))) {
            throw new ApiException(HttpStatus.CONFLICT, "BINDING_ALREADY_ACTIVE", "双方已经绑定");
        }
        requireNoOtherActiveBinding(person.id(), targetUserId);
        Map<String, Object> invitation = relationshipRepository.upsertPendingInvitation(person.id(), targetUserId);
        return invitationDto(invitationWithPeople(invitation, target), false);
    }

    // 这个函数接受别人发来的绑定邀请，并激活双向绑定。
    public Map<String, Object> acceptInvitation(CurrentPerson person, String bindingId) {
        Map<String, Object> invitation = requirePendingInvitation(bindingId);
        if (!person.id().equals(String.valueOf(invitation.get("target_user_id")))) {
            throw new ApiException(HttpStatus.FORBIDDEN, "FORBIDDEN", "只能处理发给自己的绑定邀请");
        }
        String requesterUserId = String.valueOf(invitation.get("requester_user_id"));
        requireNoOtherActiveBinding(person.id(), requesterUserId);
        relationshipRepository.ensureActiveBinding(requesterUserId, person.id());
        relationshipRepository.ensureActiveBinding(person.id(), requesterUserId);
        return binding(person);
    }

    // 这个函数拒绝别人发来的绑定邀请。
    public Map<String, Object> rejectInvitation(CurrentPerson person, String bindingId) {
        Map<String, Object> invitation = requirePendingInvitation(bindingId);
        if (!person.id().equals(String.valueOf(invitation.get("target_user_id")))) {
            throw new ApiException(HttpStatus.FORBIDDEN, "FORBIDDEN", "只能拒绝发给自己的绑定邀请");
        }
        relationshipRepository.updateBindingStatus(bindingId, "declined");
        return binding(person);
    }

    // 这个函数取消自己发出的绑定邀请。
    public Map<String, Object> cancelInvitation(CurrentPerson person, String bindingId) {
        Map<String, Object> invitation = requirePendingInvitation(bindingId);
        if (!person.id().equals(String.valueOf(invitation.get("requester_user_id")))) {
            throw new ApiException(HttpStatus.FORBIDDEN, "FORBIDDEN", "只能取消自己发出的绑定邀请");
        }
        relationshipRepository.updateBindingStatus(bindingId, "cancelled");
        return binding(person);
    }

    // 这个函数要求当前用户已经切换到绑定管理员视角。
    public String requireBoundAdminTarget(CurrentPerson person) {
        if (!VIEW_BOUND_ADMIN.equals(currentViewRole(person))) {
            throw new ApiException(HttpStatus.FORBIDDEN, "FORBIDDEN", "请先切换到绑定管理员视角");
        }
        return requireBoundTarget(person);
    }

    // 这个函数要求当前用户存在绑定对象，并返回绑定对象 ID。
    public String requireBoundTarget(CurrentPerson person) {
        if (person.isOpsAdmin()) {
            throw new ApiException(HttpStatus.FORBIDDEN, "FORBIDDEN", "后台人员不能作为绑定管理员");
        }
        Map<String, Object> binding = relationshipRepository.activeBinding(person.id());
        if (binding.isEmpty()) {
            throw new ApiException(HttpStatus.FORBIDDEN, "FORBIDDEN", "当前用户没有绑定对象");
        }
        return String.valueOf(binding.get("target_user_id"));
    }

    // 这个函数判断并返回当前视角对应的数据拥有者。
    public String ownerForCurrentView(CurrentPerson person) {
        if (VIEW_BOUND_ADMIN.equals(currentViewRole(person))) {
            return requireBoundTarget(person);
        }
        return person.id();
    }

    // 这个函数校验指定用户是否是当前用户绑定对象。
    public void requireCanManageTarget(CurrentPerson person, String targetUserId) {
        if (!relationshipRepository.isBoundTarget(person.id(), targetUserId)) {
            throw new ApiException(HttpStatus.FORBIDDEN, "FORBIDDEN", "只能操作绑定用户的数据");
        }
    }

    // 这个函数读取当前持久化视角。
    public String currentViewRole(CurrentPerson person) {
        if (person.isOpsAdmin()) {
            return VIEW_OPS_ADMIN;
        }
        Map<String, Object> row = identityRepository.person(person.id());
        Object value = row.get("current_view_role");
        String normalized = value == null ? VIEW_USER : normalizeViewRole(String.valueOf(value));
        if (VIEW_BOUND_ADMIN.equals(normalized) && relationshipRepository.activeBinding(person.id()).isEmpty()) {
            return VIEW_USER;
        }
        return normalized;
    }

    // 这个函数把用户行转换成前端 DTO。
    public Map<String, Object> personDto(String id, String displayName, String role) {
        return dto("id", id, "displayName", displayName, "role", role, "enabled", true);
    }

    private Map<String, Object> invitationDto(Map<String, Object> row, boolean incoming) {
        return dto(
                "id", row.get("id"),
                "status", row.get("status"),
                "requester", personDto(
                        String.valueOf(row.get("requester_user_id")),
                        String.valueOf(row.getOrDefault("requester_display_name", incoming ? row.get("requester_user_id") : "")),
                        String.valueOf(row.getOrDefault("requester_role", "USER")),
                        row.get("requester_login_name")
                ),
                "target", personDto(
                        String.valueOf(row.get("target_user_id")),
                        String.valueOf(row.getOrDefault("target_display_name", incoming ? "" : row.get("target_user_id"))),
                        String.valueOf(row.getOrDefault("target_role", "USER")),
                        row.get("target_login_name")
                ),
                "createdAt", row.get("created_at"),
                "updatedAt", row.get("updated_at")
        );
    }

    private Map<String, Object> invitationWithPeople(Map<String, Object> invitation, Map<String, Object> targetAccount) {
        Map<String, Object> requester = relationshipRepository.person(String.valueOf(invitation.get("requester_user_id")));
        Map<String, Object> target = relationshipRepository.person(String.valueOf(invitation.get("target_user_id")));
        Map<String, Object> source = new LinkedHashMap<>(invitation);
        source.put("requester_display_name", requester.get("display_name"));
        source.put("requester_role", requester.get("role"));
        source.put("target_display_name", target.get("display_name"));
        source.put("target_role", target.get("role"));
        source.put("target_login_name", targetAccount.get("login_name"));
        return source;
    }

    private Map<String, Object> personDto(String id, String displayName, String role, Object loginName) {
        Map<String, Object> dto = new LinkedHashMap<>(personDto(id, displayName, role));
        if (loginName != null && !String.valueOf(loginName).isBlank()) {
            dto.put("loginName", loginName);
        }
        return dto;
    }

    private void requireNoOtherActiveBinding(String requesterUserId, String targetUserId) {
        Map<String, Object> requesterBinding = relationshipRepository.activeBinding(requesterUserId);
        if (!requesterBinding.isEmpty() && !targetUserId.equals(String.valueOf(requesterBinding.get("target_user_id")))) {
            throw new ApiException(HttpStatus.CONFLICT, "BINDING_ALREADY_ACTIVE", "当前用户已经有绑定对象");
        }
        Map<String, Object> targetBinding = relationshipRepository.activeBinding(targetUserId);
        if (!targetBinding.isEmpty() && !requesterUserId.equals(String.valueOf(targetBinding.get("target_user_id")))) {
            throw new ApiException(HttpStatus.CONFLICT, "BINDING_TARGET_ALREADY_ACTIVE", "对方已经有绑定对象");
        }
    }

    private Map<String, Object> requirePendingInvitation(String bindingId) {
        Map<String, Object> invitation = relationshipRepository.bindingById(bindingId);
        if (invitation.isEmpty() || !"pending".equals(String.valueOf(invitation.get("status")))) {
            throw new ApiException(HttpStatus.NOT_FOUND, "BINDING_INVITATION_NOT_FOUND", "绑定邀请不存在或已处理");
        }
        return invitation;
    }

    private String normalizeLoginName(String loginName) {
        String value = loginName == null ? "" : loginName.trim().toLowerCase();
        if (!value.matches("[a-z0-9_@.\\-]{3,64}")) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "INVALID_LOGIN_NAME", "账号格式不正确");
        }
        return value;
    }

    private boolean boolValue(Object value) {
        if (value instanceof Boolean bool) {
            return bool;
        }
        return value != null && ("1".equals(String.valueOf(value)) || Boolean.parseBoolean(String.valueOf(value)));
    }

    private String normalizeViewRole(String value) {
        if ("admin".equalsIgnoreCase(value) || "BOUND_ADMIN".equalsIgnoreCase(value)) {
            return VIEW_BOUND_ADMIN;
        }
        if ("user".equalsIgnoreCase(value) || VIEW_USER.equalsIgnoreCase(value)) {
            return VIEW_USER;
        }
        throw new ApiException(HttpStatus.BAD_REQUEST, "BAD_REQUEST", "未知视角");
    }

    private Map<String, Object> dto(Object... entries) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int index = 0; index + 1 < entries.length; index += 2) {
            result.put(String.valueOf(entries[index]), entries[index + 1]);
        }
        return result;
    }

    private Map<String, Object> castMap(Map<?, ?> source) {
        Map<String, Object> result = new LinkedHashMap<>();
        source.forEach((key, value) -> result.put(String.valueOf(key), value));
        return result;
    }
}
