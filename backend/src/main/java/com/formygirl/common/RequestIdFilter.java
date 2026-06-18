package com.formygirl.common;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
public class RequestIdFilter extends OncePerRequestFilter {
    // 这个函数为每个请求补齐 requestId 并写回响应头。
    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        String requestId = request.getHeader(RequestIds.HEADER);
        if (requestId == null || requestId.isBlank()) {
            requestId = RequestIds.newRequestId();
        }
        request.setAttribute(RequestIds.ATTRIBUTE, requestId);
        response.setHeader(RequestIds.HEADER, requestId);
        filterChain.doFilter(request, response);
    }
}
