"""飞书多维表格读取相关字段说明。"""

from __future__ import annotations

from typing import Any


# 这一段记录 Router Agent 需要整理给 Read Agent 的字段，字段名贴近飞书查询记录接口。
FEISHU_READ_FIELD_SCHEMA: dict[str, Any] = {
    "path_params": {
        "app_token": "多维表格 app token，来自飞书多维表格 URL 或配置。",
        "table_id": "多维表格 table id，来自飞书多维表格 URL 或配置。",
        "record_id": "单条记录 id，仅 get_record 场景需要。",
    },
    "query_params": {
        "page_size": "分页大小，飞书查询记录接口最大 500。",
        "page_token": "分页游标，第一页为空。",
        "user_id_type": "用户 ID 类型，可选 open_id、union_id、user_id。",
    },
    "body": {
        "field_names": "需要返回的字段名列表。",
        "filter": "查询过滤条件，包含 conjunction 和 conditions。",
        "sort": "排序条件。",
        "view_id": "视图 id，可限制在指定视图读取。",
        "automatic_fields": "是否返回自动计算字段。",
    },
    "record_shape": {
        "record_id": "记录 id。",
        "fields": "记录字段名到字段值的映射。",
    },
    "filter_operators": {
        "allowed": [
            "is",
            "isNot",
            "contains",
            "doesNotContain",
            "isEmpty",
            "isNotEmpty",
            "isGreater",
            "isGreaterEqual",
            "isLess",
            "isLessEqual",
            "like",
            "in",
        ],
        "note": "飞书 search records 不接受 equals，等于请使用 is。",
    },
}


# 这一段是项目当前 mock 表格的字段别名，Router 会用它把自然语言整理成字段名。
KNOWN_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "标题": ("标题", "主题", "事项", "任务", "名称", "名字"),
    "内容": ("内容", "详情", "描述", "备注", "正文"),
    "状态": ("状态", "进度", "完成情况"),
    "分类": ("分类", "类型", "类别"),
    "优先级": ("优先级", "重要程度", "紧急程度"),
    "负责人": ("负责人", "负责", "归属人", "执行人"),
    "截止时间": ("截止时间", "截止日期", "ddl", "到期时间", "到期日期"),
    "创建时间": ("创建时间", "创建日期"),
    "更新时间": ("更新时间", "更新日期", "修改时间"),
}


# 这一段定义自然语言没有明确指定字段时的默认读取字段。
DEFAULT_READ_FIELDS = ["标题", "内容", "状态", "分类", "优先级", "截止时间"]
