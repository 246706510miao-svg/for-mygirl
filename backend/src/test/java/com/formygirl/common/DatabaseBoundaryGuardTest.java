package com.formygirl.common;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.Test;

class DatabaseBoundaryGuardTest {
    @Test
    void allowsBusinessDatabaseWithBackendUser() {
        assertDoesNotThrow(() -> DatabaseBoundaryGuard.validateBusinessDatasource(
                "jdbc:mysql://127.0.0.1:3307/for_mygirl_app?useUnicode=true",
                "backend_user"
        ));
    }

    @Test
    void rejectsThirdWorkflowDatabase() {
        assertThrows(IllegalStateException.class, () -> DatabaseBoundaryGuard.validateBusinessDatasource(
                "jdbc:mysql://127.0.0.1:3307/third_service",
                "backend_user"
        ));
    }

    @Test
    void rejectsThirdTestDatabase() {
        assertThrows(IllegalStateException.class, () -> DatabaseBoundaryGuard.validateBusinessDatasource(
                "jdbc:mysql://127.0.0.1:3307/third_test",
                "backend_user"
        ));
    }

    @Test
    void rejectsThirdUserAccount() {
        assertThrows(IllegalStateException.class, () -> DatabaseBoundaryGuard.validateBusinessDatasource(
                "jdbc:mysql://127.0.0.1:3307/for_mygirl_app",
                "third_user"
        ));
    }

    @Test
    void rejectsUnknownMysqlDatabase() {
        assertThrows(IllegalStateException.class, () -> DatabaseBoundaryGuard.validateBusinessDatasource(
                "jdbc:mysql://127.0.0.1:3307/other_app",
                "backend_user"
        ));
    }
}
