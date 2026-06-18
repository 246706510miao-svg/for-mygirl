package com.formygirl.relationship;

import com.formygirl.common.ApiResponse;
import com.formygirl.common.RequestIds;
import com.formygirl.identity.CurrentPerson;
import com.formygirl.identity.IdentityService;
import jakarta.servlet.http.HttpServletRequest;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestHeader;
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
    public ApiResponse<Map<String, Object>> binding(@RequestHeader("Authorization") String authorization, HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(authorization);
        return ApiResponse.ok(relationshipService.binding(person), String.valueOf(request.getAttribute(RequestIds.ATTRIBUTE)));
    }
}
