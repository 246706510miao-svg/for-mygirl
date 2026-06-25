package com.formygirl.relationship;

import com.formygirl.common.ApiResponse;
import com.formygirl.common.RequestIds;
import com.formygirl.identity.CurrentPerson;
import com.formygirl.identity.IdentityService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class RelationshipController {
    private final IdentityService identityService;
    private final RelationshipService relationshipService;

    public RelationshipController(IdentityService identityService, RelationshipService relationshipService) {
        this.identityService = identityService;
        this.relationshipService = relationshipService;
    }

    // 这个接口返回当前用户的绑定对象和授权能力。
    @GetMapping("/api/relationship/binding")
    public ApiResponse<Map<String, Object>> binding(HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        return ApiResponse.ok(relationshipService.binding(person), String.valueOf(request.getAttribute(RequestIds.ATTRIBUTE)));
    }

    // 这个接口向另一个账号发起绑定邀请。
    @PostMapping("/api/relationship/invitations")
    public ApiResponse<Map<String, Object>> invite(@Valid @RequestBody InviteRequest body, HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        return ApiResponse.created(relationshipService.invite(person, body.targetLoginName()), String.valueOf(request.getAttribute(RequestIds.ATTRIBUTE)));
    }

    // 这个接口接受发给当前用户的绑定邀请。
    @PostMapping("/api/relationship/invitations/{bindingId}/accept")
    public ApiResponse<Map<String, Object>> accept(@PathVariable String bindingId, HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        return ApiResponse.ok(relationshipService.acceptInvitation(person, bindingId), String.valueOf(request.getAttribute(RequestIds.ATTRIBUTE)));
    }

    // 这个接口拒绝发给当前用户的绑定邀请。
    @PostMapping("/api/relationship/invitations/{bindingId}/reject")
    public ApiResponse<Map<String, Object>> reject(@PathVariable String bindingId, HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        return ApiResponse.ok(relationshipService.rejectInvitation(person, bindingId), String.valueOf(request.getAttribute(RequestIds.ATTRIBUTE)));
    }

    // 这个接口取消当前用户发出的绑定邀请。
    @PostMapping("/api/relationship/invitations/{bindingId}/cancel")
    public ApiResponse<Map<String, Object>> cancel(@PathVariable String bindingId, HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        return ApiResponse.ok(relationshipService.cancelInvitation(person, bindingId), String.valueOf(request.getAttribute(RequestIds.ATTRIBUTE)));
    }

    public record InviteRequest(@NotBlank String targetLoginName) {
    }
}
