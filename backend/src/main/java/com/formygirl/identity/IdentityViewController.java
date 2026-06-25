package com.formygirl.identity;

import com.formygirl.common.ApiResponse;
import com.formygirl.common.RequestIds;
import com.formygirl.relationship.RelationshipService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import java.util.Map;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class IdentityViewController {
    private final IdentityService identityService;
    private final RelationshipService relationshipService;

    public IdentityViewController(IdentityService identityService, RelationshipService relationshipService) {
        this.identityService = identityService;
        this.relationshipService = relationshipService;
    }

    // 这个接口在用户视角和绑定管理员视角之间切换。
    @PostMapping("/api/identity/view-role")
    public ApiResponse<Map<String, Object>> switchView(@Valid @RequestBody ViewRoleRequest body, HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        return ApiResponse.ok(relationshipService.switchViewRole(person, body.viewRole()), String.valueOf(request.getAttribute(RequestIds.ATTRIBUTE)));
    }

    public record ViewRoleRequest(@NotBlank String viewRole) {
    }
}
