package com.formygirl;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class ForMyGirlBackendApplication {
    // 这个函数启动 SpringBoot 业务后端。
    public static void main(String[] args) {
        SpringApplication.run(ForMyGirlBackendApplication.class, args);
    }
}
