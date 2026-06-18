/**
 * 同步模块：负责飞书 payload、同步状态、失败保留和重试策略。
 *
 * <p>后台运维可以调用同步能力重写入或重试，但具体同步状态和 payload 归本模块维护。
 */
package com.formygirl.sync;
