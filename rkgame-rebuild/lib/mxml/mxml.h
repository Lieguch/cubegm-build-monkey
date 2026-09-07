/* ============================================================
 * mxml.h - 简化版 mxml XML 解析库（基于原厂反编译）
 * ============================================================
 *
 * 原厂 mxml 符号分析：102 个符号，19 KB
 * 关键函数：mxml_load_data, mxml_write_node, mxmlFindElement, ...
 *
 * 本实现：简化版，支持基本 XML 解析（setting.xml）
 * 目标：100% 还原原厂功能
 * ============================================================ */

#ifndef MXML_H
#define MXML_H

#ifdef __cplusplus
extern "C" {
#endif

/* XML 节点类型 */
typedef enum {
    MXML_ELEMENT = 1,    /* 元素节点 */
    MXML_TEXT = 2,       /* 文本节点 */
    MXML_COMMENT = 3,    /* 注释节点 */
    MXML_DOCTYPE = 4,    /* DOCTYPE 节点 */
    MXML_DATA = 5,       /* DATA 节点 */
    MXML_WHITESPACE = 6  /* 空白节点 */
} mxml_type_t;

/* XML 节点结构 */
typedef struct mxml_node_s {
    struct mxml_node_s *parent;    /* 父节点 */
    struct mxml_node_s *child;     /* 第一个子节点 */
    struct mxml_node_s *next;      /* 下一个兄弟节点 */
    struct mxml_node_s *prev;      /* 上一个兄弟节点 */
    struct mxml_node_s *last;      /* 最后一个子节点 */
    
    mxml_type_t type;              /* 节点类型 */
    char *value;                   /* 节点值（元素名或文本内容） */
    
    unsigned int namespace;        /* 命名空间（未使用） */
    
    void *parent_priv;             /* 父节点私有数据 */
    void *priv;                    /* 私有数据 */
    
    /* 元素属性 */
    char **elements;               /* 属性名数组 */
    char **values;                 /* 属性值数组 */
    unsigned int num_attrs;        /* 属性数量 */
    
    /* 文本内容 */
    char *content;                 /* 文本内容 */
    unsigned int content_len;      /* 文本内容长度 */
} mxml_node_t;

/* XML 解析器上下文 */
typedef struct {
    const char *data;              /* 输入数据 */
    unsigned int pos;              /* 当前位置 */
    unsigned int len;              /* 数据长度 */
} mxml_parser_t;

/* ---- 核心 API ---- */

/* 从数据加载 XML */
mxml_node_t *mxml_load_data(const char *data, unsigned int length);

/* 从文件加载 XML */
mxml_node_t *mxml_load_file(const char *filename);

/* 删除 XML 文档 */
void mxml_delete(mxml_node_t *node);

/* 查找元素 */
mxml_node_t *mxml_find_element(mxml_node_t *root, 
                                const char *element,
                                const char *value,
                                unsigned int index);

/* 获取属性值 */
const char *mxml_get_attr(const mxml_node_t *node, const char *name);

/* 设置属性值 */
void mxml_set_attr(mxml_node_t *node, const char *name, const char *value);

/* 获取元素文本内容 */
const char *mxml_get_content(const mxml_node_t *node);

/* 遍历子节点 */
mxml_node_t *mxml_first_child(const mxml_node_t *node);
mxml_node_t *mxml_next_sibling(const mxml_node_t *node);
mxml_node_t *mxml_last_child(const mxml_node_t *node);

/* ---- 内部函数 ---- */

/* 解析属性 */
void mxml_parse_attrs(mxml_parser_t *parser, mxml_node_t *node);

/* 跳过空白 */
void mxml_skip_whitespace(mxml_parser_t *parser);

/* 读取字符串 */
char *mxml_read_string(mxml_parser_t *parser, const char *delim);

/* 解析元素 */
mxml_node_t *mxml_parse_element(mxml_parser_t *parser);

#ifdef __cplusplus
}
#endif

#endif /* MXML_H */
