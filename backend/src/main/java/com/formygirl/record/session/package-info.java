/**
 * 记录会话入口：负责创建会话、接收用户消息、查询会话、确认和取消。
 *
 * <p>如果排查“用户输入到草稿确认”的接口问题，从本包 Controller 进入，再追到 record 服务和 persistence。
 */
package com.formygirl.record.session;
