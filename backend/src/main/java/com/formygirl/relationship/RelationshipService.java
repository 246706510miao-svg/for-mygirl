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
            return dto("active", false, "boundUser", null, "permissions", List.of());
        }
        Map<String, Object> binding = relationshipRepository.activeBinding(person.id());
        if (binding.isEmpty()) {
            return dto("active", false, "boundUser", null, "permissions", List.of());
        }
        String bindingId = String.valueOf(binding.get("id"));
        String targetUserId = String.valueOf(binding.get("target_user_id"));
        return dto(
                "active", true,
                "bindingId", bindingId,
                "boundUser", personDto(targetUserId, String.valueOf(binding.get("target_display_name")), String.valueOf(binding.get("target_role"))),
                "permissions", relationshipRepository.permissions(bindingId, person.id())
        );
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
        return value == null ? VIEW_USER : normalizeViewRole(String.valueOf(value));
    }

    // 这个函数把用户行转换成前端 DTO。
    public Map<String, Object> personDto(String id, String displayName, String role) {
        return dto("id", id, "displayName", displayName, "role", role, "enabled", true);
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
