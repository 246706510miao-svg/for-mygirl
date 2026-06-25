package com.formygirl.comment;

import com.formygirl.common.ApiResponse;
import com.formygirl.common.RequestIds;
import com.formygirl.identity.CurrentPerson;
import com.formygirl.identity.IdentityService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import java.util.Map;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class CommentController {
    private final IdentityService identityService;
    private final CommentService commentService;

    public CommentController(IdentityService identityService, CommentService commentService) {
        this.identityService = identityService;
        this.commentService = commentService;
    }

    // 这个接口保存绑定管理员对记录的评论和打分。
    @PostMapping("/api/records/{recordId}/comment")
    public ApiResponse<Map<String, Object>> save(@PathVariable String recordId, @Valid @RequestBody CommentRequest body, HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        return ApiResponse.ok(commentService.save(person, recordId, body.content(), body.score()), String.valueOf(request.getAttribute(RequestIds.ATTRIBUTE)));
    }

    public record CommentRequest(@NotBlank String content, @Min(0) @Max(100) int score) {
    }
}
