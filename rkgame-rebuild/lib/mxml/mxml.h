/* ============================================================
 * mxml.h - mxml XML 解析库 API（统一声明）
 * ============================================================
 *
 * 原厂 mxml 符号分析：102 个符号，19 KB
 * 关键函数：mxml_load_data, mxml_write_node, mxmlFindElement, ...
 *
 * 本实现：mxml.c 含两套代码：
 *   Part 1（简化版，用 child/next/elements[]/values[]）
 *   Part 2（upstream 风格，用 first_child/next_sibling/attrs[]）
 * 本头文件声明两套结构体字段，让 mxml.c 两套代码都能编译通过。
 * rkgame src 仅使用 Part 1 API（mxml_get_attr / mxml_get_content 等）。
 * ============================================================ */

#ifndef MXML_H
#define MXML_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ---- 常量 ---- */
#define MXML_MAX_ATTRS  32

/* ---- 节点类型（Part 1 简化版） ---- */
typedef enum {
    MXML_NONE = 0,
    MXML_ELEMENT = 1,
    MXML_TEXT = 2,
    MXML_COMMENT = 3,
    MXML_DOCTYPE = 4,
    MXML_DATA = 5,
    MXML_WHITESPACE = 6,
    MXML_CDATA = 7,
    MXML_DECL = 8,
    MXML_PI = 9,
    MXML_DOCUMENT = 10
} mxml_type_t;

/* ---- 节点类型（Part 2 upstream 风格别名） ---- */
typedef mxml_type_t mxml_node_type_t;

/* ---- 属性结构（Part 2） ---- */
typedef struct _mxml_attr_s {
    char *name;
    char *value;
} mxml_attr_t;

/* ---- XML 节点结构（统一，含 Part 1 + Part 2 字段） ---- */
typedef struct mxml_node_s {
    /* Part 1 字段 */
    struct mxml_node_s *parent;
    struct mxml_node_s *child;        /* 第一个子节点 */
    struct mxml_node_s *next;         /* 下一个兄弟节点 */
    struct mxml_node_s *prev;         /* 上一个兄弟节点 */
    struct mxml_node_s *last;         /* 最后一个子节点 */
    mxml_type_t type;
    char *value;                       /* 元素名或文本内容 */
    unsigned int namespace;
    void *parent_priv;
    void *priv;
    char **elements;                   /* 属性名数组 */
    char **values;                     /* 属性值数组 */
    unsigned int num_attrs;
    char *content;                     /* 文本内容缓冲区 */
    unsigned int content_len;

    /* Part 2 字段（upstream mxml 2.x 风格） */
    struct mxml_node_s *first_child;
    struct mxml_node_s *last_child;
    struct mxml_node_s *prev_sibling;
    struct mxml_node_s *next_sibling;
    char *element;                     /* 元素名 */
    int indent;
    void *data;
    mxml_attr_t attrs[MXML_MAX_ATTRS];
} mxml_node_t;

/* ---- XML 解析器上下文 ---- */
typedef struct {
    const char *data;
    unsigned int pos;
    unsigned int len;
} mxml_parser_t;

/* ---- XML 索引 ---- */
typedef struct mxml_index_s {
    struct mxml_index_s *parent;
    char *key;
    mxml_node_t **nodes;
    unsigned int count;
    unsigned int capacity;
} mxml_index_t;

/* ---- getc 函数指针 ---- */
typedef int (*mxml_getc_cb_t)(void *cookie);

/* ---- 内部结构：stream context（Part 2 用） ---- */
typedef struct _mxml_string_s {
    const char *s;
    size_t len;
    size_t pos;
} mxml_string_t;

/* ============================================================
 * Part 1 API（简化版，rkgame src 实际使用）
 * ============================================================ */

mxml_node_t *mxml_load_data(const char *data, unsigned int length);
mxml_node_t *mxml_load_file(const char *filename);
void          mxml_delete(mxml_node_t *node);
mxml_node_t *mxml_find_element(mxml_node_t *root,
                                const char *element,
                                const char *value,
                                unsigned int index);
const char   *mxml_get_attr(const mxml_node_t *node, const char *name);
void          mxml_set_attr(mxml_node_t *node, const char *name, const char *value);
const char   *mxml_get_content(const mxml_node_t *node);
mxml_node_t  *mxml_first_child(const mxml_node_t *node);
mxml_node_t  *mxml_next_sibling(const mxml_node_t *node);
mxml_node_t  *mxml_last_child(const mxml_node_t *node);
mxml_node_t  *mxml_new_node(mxml_node_t *parent, mxml_type_t type, const char *value);
void          mxml_free(mxml_node_t *root);
mxml_node_t  *mxml_load(const char *filename);
mxml_node_t  *mxml_load_string(const char *str);
mxml_node_t  *mxmlFindElement(mxml_node_t *node, const char *name,
                             const char *element,
                             const char *attr, const char *value,
                             unsigned int index);
mxml_node_t  *mxmlFindPath(mxml_node_t *root, const char *path);
mxml_node_t  *mxml_add_char(mxml_node_t *node, int ch);
int           mxml_write_node(mxml_node_t *node, const char *pad, unsigned int depth,
                              unsigned int flags, char *buf, unsigned int buflen);
int           mxml_save(mxml_node_t *root, void *fp);
const char   *mxml_get_entity(const char *value);
int           mxml_unescape(const char *in, char *out, unsigned int outsz);
mxml_index_t *mxmlIndexNew(mxml_node_t *root, const char *name);
mxml_node_t  *mxmlIndexFind(mxml_index_t *idx, const char *value);
void          mxmlIndexDelete(mxml_index_t *idx);
unsigned int  mxml_set_indent(unsigned int flags);
unsigned int  mxml_get_indent(void);
int           mxml_fd_getc(void *cookie);
int           mxml_file_getc(void *cookie);
int           mxml_string_getc(void *cookie);

/* ---- Part 1 内部函数 ---- */
void          mxml_parse_attrs(mxml_parser_t *parser, mxml_node_t *node);
void          mxml_skip_whitespace(mxml_parser_t *parser);
char         *mxml_read_string(mxml_parser_t *parser, const char *delim);
mxml_node_t  *mxml_parse_element(mxml_parser_t *parser);

/* ============================================================
 * Part 2 API（upstream mxml 2.x 风格，符号完整性用）
 * ============================================================ */

/* 子节点操作 */
unsigned int       mxml_get_child_count(const mxml_node_t *node);
unsigned int       mxml_get_num_children(const mxml_node_t *node);
mxml_node_t       *mxml_get_child(const mxml_node_t *node, unsigned int index);
const mxml_node_t *mxml_get_parent(const mxml_node_t *node);
const mxml_node_t *mxml_get_prev_sibling(const mxml_node_t *node);
const mxml_node_t *mxml_get_next_sibling(const mxml_node_t *node);

/* 节点属性 */
void               mxml_set_content(mxml_node_t *node, const char *content);
void               mxml_set_type(mxml_node_t *node, mxml_type_t type);
mxml_type_t        mxml_get_type(const mxml_node_t *node);
void               mxml_set_data(mxml_node_t *node, void *data);
void              *mxml_get_data(const mxml_node_t *node);
void               mxml_set_value(mxml_node_t *node, const char *value);
const char        *mxml_get_value(const mxml_node_t *node);
void               mxml_release_data(mxml_node_t *node);

/* 属性操作 */
unsigned int       mxml_get_num_attrs(const mxml_node_t *node);
void               mxml_set_num_attrs(mxml_node_t *node, unsigned int count);
const char        *mxml_get_attr_name(const mxml_node_t *node, unsigned int index);
const char        *mxml_get_attr_value(const mxml_node_t *node, unsigned int index);
void               mxml_add_attr(mxml_node_t *node, const char *name, const char *value);
void               mxml_delete_attr(mxml_node_t *node, unsigned int index);
void               mxml_release_attr(mxml_node_t *node, unsigned int index);

/* 树操作 */
mxml_node_t       *mxml_add_child(mxml_node_t *parent, mxml_node_t *child);
mxml_node_t       *mxml_add_sibling(mxml_node_t *node, mxml_node_t *sibling);
void               mxml_remove_child(mxml_node_t *parent, mxml_node_t *child);
void               mxml_remove_sibling(mxml_node_t *node);
mxml_node_t       *mxml_release_child(mxml_node_t *parent, mxml_node_t *child);
mxml_node_t       *mxml_release_sibling(mxml_node_t *node);

/* 创建节点 */
mxml_node_t       *mxml_new_text_node(mxml_node_t *parent, const char *text);
mxml_node_t       *mxml_new_element(mxml_node_t *parent, const char *name,
                                    const char *value, const char **attrs);
mxml_node_t       *mxml_new_cdata(mxml_node_t *parent, const char *text);
mxml_node_t       *mxml_new_comment(mxml_node_t *parent, const char *text);
mxml_node_t       *mxml_new_decl(mxml_node_t *parent, const char *version,
                                 const char *encoding);
mxml_node_t       *mxml_new_doc(const char *version);
mxml_node_t       *mxml_new_pi(mxml_node_t *parent, const char *target,
                              const char *data);

/* 节点释放 / 字符数据 */
void               mxml_release_node(mxml_node_t *node);
void               mxml_set_char_data(mxml_node_t *node, const char *data, unsigned int len);
const char        *mxml_get_char_data(const mxml_node_t *node);
unsigned int       mxml_get_char_len(const mxml_node_t *node);

#ifdef __cplusplus
}
#endif

#endif /* MXML_H */
