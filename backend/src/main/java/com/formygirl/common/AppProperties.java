package com.formygirl.common;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "app")
public class AppProperties {
    private String corsOrigin;
    private String secretKey;
    private String adminInitialPassword;
    private String legacyUserLoginName;
    private String legacyUserInitialPassword;
    private String legacyPartnerLoginName;
    private String legacyPartnerInitialPassword;
    private int sessionTtlHours;
    private String authCookieName;
    private boolean authCookieSecure;
    private String thirdBaseUrl;
    private int thirdPollTimes;
    private long thirdPollIntervalMs;

    public String getCorsOrigin() {
        return corsOrigin;
    }

    public void setCorsOrigin(String corsOrigin) {
        this.corsOrigin = corsOrigin;
    }

    public String getSecretKey() {
        return secretKey;
    }

    public void setSecretKey(String secretKey) {
        this.secretKey = secretKey;
    }

    public String getAdminInitialPassword() {
        return adminInitialPassword;
    }

    public void setAdminInitialPassword(String adminInitialPassword) {
        this.adminInitialPassword = adminInitialPassword;
    }

    public String getLegacyUserLoginName() {
        return legacyUserLoginName;
    }

    public void setLegacyUserLoginName(String legacyUserLoginName) {
        this.legacyUserLoginName = legacyUserLoginName;
    }

    public String getLegacyUserInitialPassword() {
        return legacyUserInitialPassword;
    }

    public void setLegacyUserInitialPassword(String legacyUserInitialPassword) {
        this.legacyUserInitialPassword = legacyUserInitialPassword;
    }

    public String getLegacyPartnerLoginName() {
        return legacyPartnerLoginName;
    }

    public void setLegacyPartnerLoginName(String legacyPartnerLoginName) {
        this.legacyPartnerLoginName = legacyPartnerLoginName;
    }

    public String getLegacyPartnerInitialPassword() {
        return legacyPartnerInitialPassword;
    }

    public void setLegacyPartnerInitialPassword(String legacyPartnerInitialPassword) {
        this.legacyPartnerInitialPassword = legacyPartnerInitialPassword;
    }

    public int getSessionTtlHours() {
        return sessionTtlHours;
    }

    public void setSessionTtlHours(int sessionTtlHours) {
        this.sessionTtlHours = sessionTtlHours;
    }

    public String getAuthCookieName() {
        return authCookieName;
    }

    public void setAuthCookieName(String authCookieName) {
        this.authCookieName = authCookieName;
    }

    public boolean isAuthCookieSecure() {
        return authCookieSecure;
    }

    public void setAuthCookieSecure(boolean authCookieSecure) {
        this.authCookieSecure = authCookieSecure;
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
