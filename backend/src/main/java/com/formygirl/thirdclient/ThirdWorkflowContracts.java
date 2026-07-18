package com.formygirl.thirdclient;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonValue;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.List;
import java.util.Map;

public final class ThirdWorkflowContracts {
    private ThirdWorkflowContracts() {
    }

    public enum WorkflowStatus {
        QUEUED("queued"),
        RUNNING("running"),
        WAITING_USER("waiting_user"),
        SUCCESS("success"),
        FAILED("failed"),
        CANCELLED("cancelled");

        private final String value;

        WorkflowStatus(String value) {
            this.value = value;
        }

        @JsonCreator
        public static WorkflowStatus fromValue(String value) {
            for (WorkflowStatus candidate : values()) {
                if (candidate.value.equals(value)) {
                    return candidate;
                }
            }
            throw new IllegalArgumentException("不支持的 workflow status：" + value);
        }

        @JsonValue
        public String value() {
            return value;
        }
    }

    public enum InteractionKind {
        CLARIFY("clarify"),
        CONFIRM("confirm"),
        CHOOSE_CANDIDATE("choose_candidate");

        private final String value;

        InteractionKind(String value) {
            this.value = value;
        }

        @JsonCreator
        public static InteractionKind fromValue(String value) {
            for (InteractionKind candidate : values()) {
                if (candidate.value.equals(value)) {
                    return candidate;
                }
            }
            throw new IllegalArgumentException("不支持的 interaction kind：" + value);
        }

        @JsonValue
        public String value() {
            return value;
        }
    }

    public enum InteractionResponse {
        APPROVE("approve"),
        ANSWER("answer"),
        MODIFY("modify"),
        CANCEL("cancel");

        private final String value;

        InteractionResponse(String value) {
            this.value = value;
        }

        @JsonCreator
        public static InteractionResponse fromValue(String value) {
            for (InteractionResponse candidate : values()) {
                if (candidate.value.equals(value)) {
                    return candidate;
                }
            }
            throw new IllegalArgumentException("不支持的 interaction response：" + value);
        }

        @JsonValue
        public String value() {
            return value;
        }
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record ContentPart(String text) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record FeishuPublicMetadata(
            String configId,
            String displayName,
            String tableId,
            String viewId
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record WorkflowMetadata(
            String businessSessionId,
            String businessRecordId,
            String operation,
            String mode,
            String idempotencyKey,
            FeishuPublicMetadata feishu
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record FeishuAccountMetadata(
            boolean enabled,
            String appId,
            String appSecret,
            String tenantAccessToken,
            String userIdType
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record FeishuTableMetadata(
            boolean enabled,
            String displayName,
            String appToken,
            String tableId,
            String tableName,
            String viewId,
            JsonNode fieldNameMap
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record FeishuPrivateMetadata(
            String configId,
            FeishuAccountMetadata account,
            FeishuTableMetadata table
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record WorkflowPrivateMetadata(FeishuPrivateMetadata feishu) {
        public static WorkflowPrivateMetadata empty() {
            return new WorkflowPrivateMetadata(null);
        }
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record InvokeWorkflowRequest(
            List<ContentPart> content,
            WorkflowMetadata metadata,
            WorkflowPrivateMetadata privateMetadata
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record ResumeWorkflowRequest(
            String confirmationId,
            boolean approved,
            InteractionResponse response,
            List<ContentPart> content
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record FeishuTableCheckRequest(WorkflowPrivateMetadata privateMetadata) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record WorkflowResponse(
            String sessionId,
            WorkflowStatus status,
            List<ContentPart> content,
            String errorText
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record SnapshotSession(
            String sessionId,
            WorkflowStatus status,
            String currentStepId,
            String originalInput,
            String finalAnswer,
            String errorText,
            WorkflowMetadata metadata,
            String createdAt,
            String updatedAt
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record WorkflowDecision(
            String planId,
            JsonNode planVersion,
            String templateKey,
            String intent,
            String riskLevel,
            boolean requiresConfirmation,
            @JsonProperty("final") JsonNode finalValue
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record WorkflowConfirmation(
            String confirmationId,
            String status,
            String requestText,
            JsonNode preview,
            String stepId,
            String userResponse,
            InteractionKind interactionKind,
            List<JsonNode> options,
            String createdAt,
            String decidedAt,
            String expiresAt
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record WorkflowOutputs(
            JsonNode draft,
            JsonNode writePayload,
            JsonNode writeResult,
            JsonNode tableSchema,
            JsonNode records,
            JsonNode finalAnswer
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record WorkflowArtifact(
            String artifactId,
            String sessionId,
            String sourceStepId,
            String artifactKey,
            String contentText,
            JsonNode data,
            JsonNode schema,
            String createdAt,
            String expiresAt
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record WorkflowSnapshot(
            SnapshotSession session,
            WorkflowDecision decision,
            WorkflowConfirmation confirmation,
            WorkflowOutputs outputs,
            Map<String, WorkflowArtifact> artifactsByKey,
            List<WorkflowArtifact> artifacts
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record WorkflowTimeline(
            SnapshotSession session,
            WorkflowDecision decision,
            List<JsonNode> steps,
            List<WorkflowConfirmation> confirmations,
            List<WorkflowArtifact> artifacts
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record WorkflowArtifacts(
            String sessionId,
            List<WorkflowArtifact> artifacts
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record FeishuTableCheckResponse(
            String status,
            String message,
            String tableName,
            int fieldCount,
            List<String> fieldNames
    ) {
    }
}
