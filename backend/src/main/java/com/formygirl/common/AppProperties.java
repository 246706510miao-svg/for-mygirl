package com.formygirl.common;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "app")
public class AppProperties {
    private String corsOrigin;
    private String userToken;
    private String adminToken;
    private String thirdBaseUrl;
    private int thirdPollTimes;
    private long thirdPollIntervalMs;

    public String getCorsOrigin() {
        return corsOrigin;
    }

    public void setCorsOrigin(String corsOrigin) {
        this.corsOrigin = corsOrigin;
    }

    public String getUserToken() {
        return userToken;
    }

    public void setUserToken(String userToken) {
        this.userToken = userToken;
    }

    public String getAdminToken() {
        return adminToken;
    }

    public void setAdminToken(String adminToken) {
        this.adminToken = adminToken;
    }

    public String getThirdBaseUrl() {
        return thirdBaseUrl;
    }

    public void setThirdBaseUrl(String thirdBaseUrl) {
        this.thirdBaseUrl = thirdBaseUrl;
    }

    public int getThirdPollTimes() {
        return thirdPollTimes;
    }

    public void setThirdPollTimes(int thirdPollTimes) {
        this.thirdPollTimes = thirdPollTimes;
    }

    public long getThirdPollIntervalMs() {
        return thirdPollIntervalMs;
    }

    public void setThirdPollIntervalMs(long thirdPollIntervalMs) {
        this.thirdPollIntervalMs = thirdPollIntervalMs;
    }
}
