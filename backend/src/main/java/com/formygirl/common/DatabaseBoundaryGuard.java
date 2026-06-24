package com.formygirl.common;

import java.util.Locale;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;

@Component
public class DatabaseBoundaryGuard implements ApplicationRunner {
    private static final String BUSINESS_DATABASE = "for_mygirl_app";

    private final Environment environment;

    public DatabaseBoundaryGuard(Environment environment) {
        this.environment = environment;
    }

    @Override
    public void run(ApplicationArguments args) {
        validateBusinessDatasource(
                environment.getProperty("spring.datasource.url", ""),
                environment.getProperty("spring.datasource.username", "")
        );
    }

    static void validateBusinessDatasource(String jdbcUrl, String username) {
        String normalizedUsername = value(username).toLowerCase(Locale.ROOT);
        if ("third_user".equals(normalizedUsername)) {
            throw new IllegalStateException("SpringBoot 不能使用 third 私有库账号 third_user；请使用 backend_user。");
        }

        String databaseName = mysqlDatabaseName(jdbcUrl);
        if (databaseName.isBlank()) {
            return;
        }
        if ("third_service".equals(databaseName) || "third_test".equals(databaseName)) {
            throw new IllegalStateException("SpringBoot 不能连接 third 私有库 " + databaseName + "。");
        }
        if (!BUSINESS_DATABASE.equals(databaseName)) {
            throw new IllegalStateException("SpringBoot 只能连接业务库 " + BUSINESS_DATABASE + "，当前为 " + databaseName + "。");
        }
    }

    private static String mysqlDatabaseName(String jdbcUrl) {
        String normalized = value(jdbcUrl).toLowerCase(Locale.ROOT);
        if (!normalized.startsWith("jdbc:mysql:")) {
            return "";
        }
        int queryIndex = normalized.indexOf('?');
        String withoutQuery = queryIndex >= 0 ? normalized.substring(0, queryIndex) : normalized;
        int slashIndex = withoutQuery.lastIndexOf('/');
        if (slashIndex < 0 || slashIndex == withoutQuery.length() - 1) {
            return "";
        }
        return withoutQuery.substring(slashIndex + 1);
    }

    private static String value(String text) {
        return text == null ? "" : text.trim();
    }
}
