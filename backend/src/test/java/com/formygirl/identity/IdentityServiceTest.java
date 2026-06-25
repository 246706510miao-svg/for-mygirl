package com.formygirl.identity;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.formygirl.common.ApiException;
import com.formygirl.common.AppProperties;
import java.time.LocalDateTime;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;

class IdentityServiceTest {
    private final IdentityRepository repository = mock(IdentityRepository.class);
    private final PasswordEncoder passwordEncoder = new BCryptPasswordEncoder();
    private final IdentityService service = new IdentityService(properties(), repository, passwordEncoder);

    @Test
    void registerStoresPasswordHashAndCreatesSession() {
        when(repository.accountByLoginName("new_user")).thenReturn(Map.of());
        when(repository.insertPerson("新人")).thenReturn(Map.of("id", "person_new"));
        when(repository.insertAccount(eq("person_new"), eq("new_user"), any())).thenReturn(account("account_new", "person_new", "new_user", "新人", passwordEncoder.encode("secret123")));

        Map<String, Object> result = service.register("New_User", "新人", "secret123");

        ArgumentCaptor<String> hashCaptor = ArgumentCaptor.forClass(String.class);
        verify(repository).insertAccount(eq("person_new"), eq("new_user"), hashCaptor.capture());
        verify(repository).insertSession(eq("account_new"), eq("person_new"), any(), any(LocalDateTime.class));
        assertFalse("secret123".equals(hashCaptor.getValue()));
        assertTrue(passwordEncoder.matches("secret123", hashCaptor.getValue()));
        assertFalse(String.valueOf(result.get("accessToken")).isBlank());
    }

    @Test
    void loginRejectsInvalidPassword() {
        when(repository.accountByLoginName("new_user")).thenReturn(account("account_new", "person_new", "new_user", "新人", passwordEncoder.encode("secret123")));

        assertThrows(ApiException.class, () -> service.login("new_user", "wrong-password"));

        verify(repository, never()).insertSession(any(), any(), any(), any());
    }

    @Test
    void logoutRevokesSessionHash() {
        service.logout("Bearer token-value");

        verify(repository).revokeSession(service.tokenHash("token-value"));
    }

    private Map<String, Object> account(String accountId, String personId, String loginName, String displayName, String passwordHash) {
        return Map.of(
                "id", accountId,
                "person_id", personId,
                "login_name", loginName,
                "password_hash", passwordHash,
                "enabled", true,
                "person_enabled", true,
                "role", "USER",
                "display_name", displayName
        );
    }

    private AppProperties properties() {
        AppProperties properties = new AppProperties();
        properties.setSessionTtlHours(1);
        return properties;
    }
}
