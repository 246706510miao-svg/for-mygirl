package com.formygirl.common;

import java.util.Arrays;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestClient;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
@EnableConfigurationProperties(AppProperties.class)
public class WebConfig {
    // 这个函数创建业务后端调用 third 使用的 HTTP 客户端。
    @Bean
    public RestClient restClient() {
        return RestClient.create();
    }

    // 这个函数配置前端开发环境跨域访问。
    @Bean
    public WebMvcConfigurer corsConfigurer(AppProperties properties) {
        return new WebMvcConfigurer() {
            @Override
            public void addCorsMappings(CorsRegistry registry) {
                registry.addMapping("/api/**")
                        .allowedOriginPatterns(corsOrigins(properties))
                        .allowedMethods("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
                        .allowedHeaders("*")
                        .exposedHeaders(RequestIds.HEADER)
                        .allowCredentials(true);
            }
        };
    }

    // 这个函数把逗号分隔的 CORS 配置转换为 Spring 可用的 origin pattern 列表。
    private String[] corsOrigins(AppProperties properties) {
        if (properties.getCorsOrigin() == null || properties.getCorsOrigin().isBlank()) {
            return new String[0];
        }
        return Arrays.stream(properties.getCorsOrigin().split(","))
                .map(String::trim)
                .filter(value -> !value.isEmpty())
                .toArray(String[]::new);
    }
}
