package com.formygirl.feishu;

import com.formygirl.common.ApiResponse;
import com.formygirl.common.RequestIds;
import com.formygirl.identity.CurrentPerson;
import com.formygirl.identity.IdentityService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class FeishuConfigController {
    private final IdentityService identityService;
    private final FeishuConfigService service;

    public FeishuConfigController(IdentityService identityService, FeishuConfigService service) {
        this.identityService = identityService;
        this.service = service;
    }

    @GetMapping("/api/user/feishu/account")
    public ApiResponse<Map<String, Object>> account(HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        return ApiResponse.ok(service.account(person.id()), requestId(request));
    }

    @PutMapping("/api/user/feishu/account")
    public ApiResponse<Map<String, Object>> saveAccount(@Valid @RequestBody AccountRequest body, HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        FeishuConfigService.AccountInput input = new FeishuConfigService.AccountInput(
                body.enabled == null || body.enabled,
                body.appId,
                body.appSecret,
                body.tenantAccessToken,
                body.userIdType
        );
        return ApiResponse.ok(service.saveAccount(person.id(), input), requestId(request));
    }

    @GetMapping("/api/user/feishu/tables")
    public ApiResponse<Map<String, Object>> tables(HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        return ApiResponse.ok(service.tables(person.id()), requestId(request));
    }

    @PostMapping("/api/user/feishu/tables")
    public ApiResponse<Map<String, Object>> createTable(@Valid @RequestBody TableRequest body, HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        FeishuConfigService.TableInput input = new FeishuConfigService.TableInput(body.displayName, body.tableUrl, body.enabled == null || body.enabled, body.fieldNameMap);
        return ApiResponse.created(service.createTable(person.id(), input), requestId(request));
    }

    @PatchMapping("/api/user/feishu/tables/{tableId}")
    public ApiResponse<Map<String, Object>> updateTable(@PathVariable String tableId, @Valid @RequestBody TableRequest body, HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        FeishuConfigService.TableInput input = new FeishuConfigService.TableInput(body.displayName, body.tableUrl, body.enabled == null || body.enabled, body.fieldNameMap);
        return ApiResponse.ok(service.updateTable(person.id(), tableId, input), requestId(request));
    }

    @PostMapping("/api/user/feishu/tables/{tableId}/default")
    public ApiResponse<Map<String, Object>> setDefault(@PathVariable String tableId, HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        return ApiResponse.ok(service.setDefault(person.id(), tableId), requestId(request));
    }

    @PostMapping("/api/user/feishu/tables/{tableId}/test")
    public ApiResponse<Map<String, Object>> testTable(@PathVariable String tableId, HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        return ApiResponse.ok(service.testTable(person.id(), tableId), requestId(request));
    }

    private String requestId(HttpServletRequest request) {
        return String.valueOf(request.getAttribute(RequestIds.ATTRIBUTE));
    }

    public static class AccountRequest {
        public Boolean enabled;
        public String appId;
        public String appSecret;
        public String tenantAccessToken;
        public String userIdType;
    }

    public static class TableRequest {
        public String displayName;
        public String tableUrl;
        public Boolean enabled;
        public Map<String, Object> fieldNameMap;
    }
}
