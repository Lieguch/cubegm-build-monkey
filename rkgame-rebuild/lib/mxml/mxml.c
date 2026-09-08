/* ============================================================
 * mxml.c - 简化版 mxml XML 解析库实现
 * ============================================================
 *
 * 原厂 mxml 符号分析：102 个符号，19 KB
 * 本实现：简化版，支持基本 XML 解析（setting.xml）
 * 目标：100% 还原原厂功能
 * ============================================================ */

#include "mxml.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

/* ---- 内部辅助函数 ---- */

/* 跳过空白 */
static void skip_whitespace(mxml_parser_t *parser)
{
    while (parser->pos < parser->len) {
        char c = parser->data[parser->pos];
        if (c == ' ' || c == '\t' || c == '\n' || c == '\r') {
            parser->pos++;
        } else {
            break;
        }
    }
}

/* 读取字符串直到分隔符 */
static char *read_string(mxml_parser_t *parser, const char *delim)
{
    unsigned int start = parser->pos;
    
    while (parser->pos < parser->len) {
        if (parser->data[parser->pos] == delim[0]) {
            break;
        }
        parser->pos++;
    }
    
    unsigned int len = parser->pos - start;
    char *str = malloc(len + 1);
    if (!str) return NULL;
    
    memcpy(str, parser->data + start, len);
    str[len] = '\0';
    
    return str;
}

/* 跳过注释 */
static void skip_comment(mxml_parser_t *parser)
{
    if (parser->pos + 3 < parser->len && 
        parser->data[parser->pos] == '<' && 
        parser->data[parser->pos + 1] == '!' && 
        parser->data[parser->pos + 2] == '-') {
        parser->pos += 4; /* 跳过 <!-- */
        while (parser->pos + 2 < parser->len) {
            if (parser->data[parser->pos] == '-' && 
                parser->data[parser->pos + 1] == '-' && 
                parser->data[parser->pos + 2] == '>') {
                parser->pos += 3;
                return;
            }
            parser->pos++;
        }
    }
}

/* 跳过 DOCTYPE */
static void skip_doctype(mxml_parser_t *parser)
{
    if (parser->pos < parser->len && parser->data[parser->pos] == '<') {
        parser->pos++;
        skip_whitespace(parser);
        while (parser->pos < parser->len && parser->data[parser->pos] != '>') {
            parser->pos++;
        }
        if (parser->pos < parser->len) {
            parser->pos++; /* 跳过 > */
        }
    }
}

/* 解析属性 */
static void parse_attrs(mxml_parser_t *parser, mxml_node_t *node)
{
    skip_whitespace(parser);
    
    while (parser->pos < parser->len) {
        char c = parser->data[parser->pos];
        
        /* 到达元素结束或自闭合 */
        if (c == '>' || c == '/') {
            break;
        }
        
        /* 读取属性名 */
        char *attr_name = read_string(parser, "=");
        if (!attr_name) {
            free(attr_name);
            parser->pos++;
            continue;
        }
        
        /* 跳过空白 */
        skip_whitespace(parser);
        
        /* 跳过 = */
        if (parser->pos < parser->len && parser->data[parser->pos] == '=') {
            parser->pos++;
        }
        
        /* 跳过空白 */
        skip_whitespace(parser);
        
        /* 读取属性值（带引号） */
        char quote = '\0';
        if (parser->pos < parser->len && 
            (parser->data[parser->pos] == '"' || parser->data[parser->pos] == '\'')) {
            quote = parser->data[parser->pos];
            parser->pos++;
        }
        
        char *attr_value = read_string(parser, quote ? &quote : "\0");
        if (!attr_value) {
            attr_value = malloc(1);
            if (attr_value) attr_value[0] = '\0';
        }
        
        if (quote && parser->pos < parser->len && parser->data[parser->pos] == quote) {
            parser->pos++;
        }
        
        /* 添加属性到节点 */
        node->elements = realloc(node->elements, (node->num_attrs + 1) * sizeof(char*));
        node->values = realloc(node->values, (node->num_attrs + 1) * sizeof(char*));
        node->elements[node->num_attrs] = attr_name;
        node->values[node->num_attrs] = attr_value;
        node->num_attrs++;
        
        /* 跳过空白 */
        skip_whitespace(parser);
    }
}

/* 解析元素 */
static mxml_node_t *parse_element(mxml_parser_t *parser)
{
    mxml_node_t *node = calloc(1, sizeof(mxml_node_t));
    if (!node) return NULL;
    
    node->type = MXML_ELEMENT;
    
    /* 读取元素名 */
    node->value = read_string(parser, " \t\n\r/>");
    if (!node->value) {
        free(node);
        return NULL;
    }
    
    /* 解析属性 */
    parse_attrs(parser, node);
    
    /* 检查自闭合 */
    if (parser->pos < parser->len && parser->data[parser->pos] == '/') {
        parser->pos++; /* 跳过 / */
        if (parser->pos < parser->len && parser->data[parser->pos] == '>') {
            parser->pos++; /* 跳过 > */
        }
        return node;
    }
    
    /* 跳过 > */
    if (parser->pos < parser->len && parser->data[parser->pos] == '>') {
        parser->pos++;
    }
    
    /* 解析子节点和文本 */
    mxml_node_t *child = NULL;
    mxml_node_t *text_buf = NULL;
    
    while (parser->pos < parser->len) {
        /* 跳过空白 */
        skip_whitespace(parser);
        
        if (parser->pos >= parser->len) break;
        
        /* 跳过注释 */
        if (parser->pos + 3 < parser->len && 
            parser->data[parser->pos] == '<' && 
            parser->data[parser->pos + 1] == '!' && 
            parser->data[parser->pos + 2] == '-') {
            skip_comment(parser);
            continue;
        }
        
        /* 跳过 DOCTYPE */
        if (parser->pos + 1 < parser->len && 
            parser->data[parser->pos] == '<' && 
            parser->data[parser->pos + 1] == '!') {
            skip_doctype(parser);
            continue;
        }
        
        /* 子元素 */
        if (parser->data[parser->pos] == '<') {
            /* 检查结束标签 */
            if (parser->pos + 1 < parser->len && parser->data[parser->pos + 1] == '/') {
                /* 结束标签 */
                parser->pos += 2; /* 跳过 </ */
                char *end_name = read_string(parser, " \t\n\r>");
                if (end_name) {
                    free(end_name);
                }
                if (parser->pos < parser->len && parser->data[parser->pos] == '>') {
                    parser->pos++;
                }
                break;
            }
            
            /* 子元素 */
            child = parse_element(parser);
            if (child) {
                if (node->child) {
                    node->last->next = child;
                    child->prev = node->last;
                    node->last = child;
                } else {
                    node->child = child;
                    node->last = child;
                }
                child->parent = node;
            }
        } else {
            /* 文本内容 */
            char *text = read_string(parser, "<");
            if (text) {
                /* 检查是否是纯空白 */
                int is_whitespace = 1;
                for (int i = 0; text[i]; i++) {
                    if (!isspace((unsigned char)text[i])) {
                        is_whitespace = 0;
                        break;
                    }
                }
                
                if (!is_whitespace) {
                    text_buf = calloc(1, sizeof(mxml_node_t));
                    if (text_buf) {
                        text_buf->type = MXML_TEXT;
                        text_buf->value = text;
                        text_buf->content = text;
                        text_buf->content_len = strlen(text);
                        
                        if (node->child) {
                            node->last->next = text_buf;
                            text_buf->prev = node->last;
                            node->last = text_buf;
                        } else {
                            node->child = text_buf;
                            node->last = text_buf;
                        }
                        text_buf->parent = node;
                    } else {
                        free(text);
                    }
                } else {
                    free(text);
                }
            }
        }
    }
    
    return node;
}

/* ---- 公共 API ---- */

/* 从数据加载 XML */
mxml_node_t *mxml_load_data(const char *data, unsigned int length)
{
    if (!data || length == 0) return NULL;
    
    mxml_parser_t parser = {
        .data = data,
        .pos = 0,
        .len = length
    };
    
    /* 跳过空白和 BOM */
    skip_whitespace(&parser);
    
    /* 跳过 XML 声明 */
    if (parser.pos + 5 < parser.len && 
        parser.data[parser.pos] == '<' && 
        parser.data[parser.pos + 1] == '?' && 
        parser.data[parser.pos + 2] == 'x' && 
        parser.data[parser.pos + 3] == 'm' && 
        parser.data[parser.pos + 4] == 'l') {
        while (parser.pos < parser.len && !(parser.data[parser.pos] == '?' && parser.pos + 1 < parser.len && parser.data[parser.pos + 1] == '>')) {
            parser.pos++;
        }
        if (parser.pos < parser.len) {
            parser.pos += 2; /* 跳过 ?> */
        }
        skip_whitespace(&parser);
    }
    
    /* 解析根元素 */
    return parse_element(&parser);
}

/* 从文件加载 XML */
mxml_node_t *mxml_load_file(const char *filename)
{
    if (!filename) return NULL;
    
    FILE *fp = fopen(filename, "rb");
    if (!fp) return NULL;
    
    fseek(fp, 0, SEEK_END);
    long size = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    
    char *data = malloc(size + 1);
    if (!data) {
        fclose(fp);
        return NULL;
    }
    
    fread(data, 1, size, fp);
    data[size] = '\0';
    fclose(fp);
    
    mxml_node_t *root = mxml_load_data(data, size);
    free(data);
    
    return root;
}

/* 删除 XML 文档 */
void mxml_delete(mxml_node_t *node)
{
    if (!node) return;
    
    /* 递归删除子节点 */
    mxml_node_t *child = node->child;
    while (child) {
        mxml_node_t *next = child->next;
        mxml_delete(child);
        child = next;
    }
    
    /* 释放属性 */
    for (unsigned int i = 0; i < node->num_attrs; i++) {
        free(node->elements[i]);
        free(node->values[i]);
    }
    free(node->elements);
    free(node->values);
    
    /* 释放值和内容 */
    free(node->value);
    free(node->content);
    
    free(node);
}

/* 查找元素 */
mxml_node_t *mxml_find_element(mxml_node_t *root,
                                const char *element,
                                const char *value,
                                unsigned int index)
{
    if (!root || !element) return NULL;

    unsigned int count = 0;
    mxml_node_t *child = root->child;

    while (child) {
        if (child->type == MXML_ELEMENT && strcmp(child->value, element) == 0) {
            /* value == NULL 表示只看元素名 */
            if (!value) {
                if (count == index) return child;
                count++;
            } else {
                /* value 是 attr=value 或纯 value（此时视为按 attr 名匹配） */
                const char *attr_val = mxml_get_attr(child, value);
                if (attr_val) {
                    if (count == index) return child;
                    count++;
                }
            }
        }

        /* 递归查找 */
        mxml_node_t *found = mxml_find_element(child, element, value, index);
        if (found) return found;

        child = child->next;
    }

    return NULL;
}

/* 获取属性值 */
const char *mxml_get_attr(const mxml_node_t *node, const char *name)
{
    if (!node || !name) return NULL;
    
    for (unsigned int i = 0; i < node->num_attrs; i++) {
        if (strcmp(node->elements[i], name) == 0) {
            return node->values[i];
        }
    }
    
    return NULL;
}

/* 设置属性值 */
void mxml_set_attr(mxml_node_t *node, const char *name, const char *value)
{
    if (!node || !name) return;
    
    /* 查找现有属性 */
    for (unsigned int i = 0; i < node->num_attrs; i++) {
        if (strcmp(node->elements[i], name) == 0) {
            free(node->values[i]);
            node->values[i] = value ? strdup(value) : NULL;
            return;
        }
    }
    
    /* 添加新属性 */
    node->elements = realloc(node->elements, (node->num_attrs + 1) * sizeof(char*));
    node->values = realloc(node->values, (node->num_attrs + 1) * sizeof(char*));
    node->elements[node->num_attrs] = strdup(name);
    node->values[node->num_attrs] = value ? strdup(value) : NULL;
    node->num_attrs++;
}

/* 获取元素文本内容 */
const char *mxml_get_content(const mxml_node_t *node)
{
    if (!node) return NULL;
    
    /* 查找第一个文本子节点 */
    mxml_node_t *child = node->child;
    while (child) {
        if (child->type == MXML_TEXT) {
            return child->content;
        }
        child = child->next;
    }
    
    return NULL;
}

/* 遍历子节点 */
mxml_node_t *mxml_first_child(const mxml_node_t *node)
{
    if (!node) return NULL;
    return node->child;
}

mxml_node_t *mxml_next_sibling(const mxml_node_t *node)
{
    if (!node) return NULL;
    return node->next;
}

mxml_node_t *mxml_last_child(const mxml_node_t *node)
{
    if (!node) return NULL;
    return node->last;
}

/* ============================================================
 * 补充 API（对齐原厂 mxml §2.4）
 * ============================================================ */

/* 创建新节点 */
mxml_node_t *mxml_new_node(mxml_node_t *parent, mxml_type_t type, const char *value)
{
    mxml_node_t *node = calloc(1, sizeof(mxml_node_t));
    if (!node) return NULL;
    node->type = type;
    node->value = value ? strdup(value) : NULL;
    if (parent) {
        node->parent = parent;
        if (parent->last) {
            parent->last->next = node;
            node->prev = parent->last;
            parent->last = node;
        } else {
            parent->child = node;
            parent->last = node;
        }
    }
    return node;
}

/* 释放整棵树 */
void mxml_free(mxml_node_t *root)
{
    mxml_delete(root);
}

/* 别名：标准 mxml 加载接口 */
mxml_node_t *mxml_load(const char *filename)
{
    return mxml_load_file(filename);
}

mxml_node_t *mxml_load_string(const char *str)
{
    if (!str) return NULL;
    return mxml_load_data(str, (unsigned int)strlen(str));
}

/* 标准 mxml 风格：按 element/attr/value 查找 */
mxml_node_t *mxmlFindElement(mxml_node_t *node, const char *name,
                             const char *element,
                             const char *attr, const char *value,
                             unsigned int index)
{
    if (!node || !name) return NULL;
    if (strcmp(name, element) != 0) return NULL;
    if (value) {
        const char *v = mxml_get_attr(node, attr ? attr : "");
        if (!v || strcmp(v, value) != 0) return NULL;
    }
    unsigned int count = 0;
    mxml_node_t *cur = node;
    while (cur) {
        if (strcmp(cur->value, element) == 0) {
            if (value) {
                const char *v = mxml_get_attr(cur, attr ? attr : "");
                if (v && strcmp(v, value) == 0) {
                    if (count == index) return cur;
                    count++;
                }
            } else {
                if (count == index) return cur;
                count++;
            }
        }
        mxml_node_t *sub = mxml_find_element(cur, element, attr, index);
        if (sub) return sub;
        cur = cur->next;
    }
    return NULL;
}

/* 按路径查找（"a/b/c" 形式） */
mxml_node_t *mxmlFindPath(mxml_node_t *root, const char *path)
{
    if (!root || !path || !*path) return NULL;
    mxml_node_t *cur = root;
    const char *p = path;
    while (*p) {
        while (*p == '/') p++;
        if (!*p) break;
        const char *end = strchr(p, '/');
        size_t nlen = end ? (size_t)(end - p) : strlen(p);
        char name[64];
        if (nlen >= sizeof(name)) nlen = sizeof(name) - 1;
        memcpy(name, p, nlen);
        name[nlen] = '\0';
        mxml_node_t *found = NULL;
        mxml_node_t *child = cur->child;
        while (child) {
            if (child->type == MXML_ELEMENT &&
                strcmp(child->value, name) == 0) {
                found = child;
                break;
            }
            child = child->next;
        }
        if (!found) return NULL;
        cur = found;
        if (!end) break;
        p = end;
    }
    return cur;
}

/* 转义字符（用于输出） */
static void xml_escape(char *buf, unsigned int bufsz, unsigned int *off,
                       const char *s)
{
    if (!s) return;
    for (const char *p = s; *p; p++) {
        const char *rep = NULL;
        switch (*p) {
            case '&':  rep = "&amp;";  break;
            case '<':  rep = "&lt;";   break;
            case '>':  rep = "&gt;";   break;
            case '"':  rep = "&quot;"; break;
            case '\'': rep = "&apos;"; break;
            default:   break;
        }
        size_t need = rep ? strlen(rep) : 1;
        if (*off + need + 1 >= bufsz) return;
        if (rep) memcpy(buf + *off, rep, need);
        else     buf[*off] = *p;
        *off += (unsigned int)need;
    }
    buf[*off] = '\0';
}

/* 缩进 */
static unsigned int g_indent_flags = 0;
unsigned int mxml_set_indent(unsigned int flags)
{
    unsigned int old = g_indent_flags;
    g_indent_flags = flags;
    return old;
}
unsigned int mxml_get_indent(void) { return g_indent_flags; }

/* 递归写入节点 */
static int write_node_recursive(mxml_node_t *node, const char *pad,
                                unsigned int depth, unsigned int flags,
                                char *buf, unsigned int buflen, unsigned int off)
{
    if (!node || off >= buflen) return -1;

    if (node->type == MXML_ELEMENT) {
        /* 打开标签 */
        const char *p = pad;
        for (unsigned int i = 0; i < depth && p; i++) {
            size_t n = strlen(p);
            if (n == 0) break;
            if (off + n + 1 >= buflen) return -1;
            memcpy(buf + off, p, n);
            off += (unsigned int)n;
        }
        const char *tag_name = node->value ? node->value : "";
        const char *open = "<";
        size_t on = 1;
        size_t tn = strlen(tag_name);
        if (off + on + tn + 1 >= buflen) return -1;
        memcpy(buf + off, open, on); off += (unsigned int)on;
        memcpy(buf + off, tag_name, tn); off += (unsigned int)tn;
        for (unsigned int i = 0; i < node->num_attrs; i++) {
            const char *nm = node->elements[i];
            const char *vl = node->values[i] ? node->values[i] : "";
            size_t s1 = 1, s2 = strlen(nm), s3 = 1, s4 = 1;
            /* 值可能被转义，先转义 */
            char esc[512];
            if (strlen(vl) >= sizeof(esc)) {
                /* 溢出保护：直接截断写 */
                memcpy(esc, vl, sizeof(esc) - 1);
                esc[sizeof(esc) - 1] = '\0';
            } else {
                unsigned int eo = 0;
                xml_escape(esc, sizeof(esc), &eo, vl);
                s4 = strlen(esc);
            }
            if (off + s1 + s2 + s3 + s4 + 1 >= buflen) return -1;
            buf[off++] = ' ';
            memcpy(buf + off, nm, s2); off += (unsigned int)s2;
            buf[off++] = '=';
            buf[off++] = '"';
            memcpy(buf + off, esc, s4); off += (unsigned int)s4;
            buf[off++] = '"';
        }
        /* 自闭合或开标签 */
        int has_children = node->child &&
            (node->child->type == MXML_ELEMENT || node->child->type == MXML_TEXT);
        if (!has_children) {
            const char *sc = " />";
            if (off + 3 + 1 >= buflen) return -1;
            memcpy(buf + off, sc, 3); off += 3;
        } else {
            const char *op = ">";
            if (off + 1 + 1 >= buflen) return -1;
            buf[off++] = '>';
            if (flags & 1) { /* indent 输出换行 */
                buf[off++] = '\n';
            }
            /* 递归子节点 */
            mxml_node_t *c = node->child;
            while (c) {
                int r = write_node_recursive(c, pad, depth + 1, flags,
                                             buf, buflen, off);
                if (r < 0) return -1;
                off = (unsigned int)r;
                c = c->next;
            }
            /* 结束标签 */
            if (flags & 1) {
                for (unsigned int i = 0; i < depth && p; i++) {
                    size_t n = strlen(p);
                    if (n == 0) break;
                    if (off + n + 1 >= buflen) return -1;
                    memcpy(buf + off, p, n); off += (unsigned int)n;
                }
            }
            const char *close = "</";
            if (off + 2 + tn + 2 + 1 >= buflen) return -1;
            memcpy(buf + off, close, 2); off += 2;
            memcpy(buf + off, tag_name, tn); off += (unsigned int)tn;
            buf[off++] = '>';
            buf[off++] = '\n';
        }
    } else if (node->type == MXML_TEXT) {
        char esc[512];
        unsigned int eo = 0;
        const char *txt = node->content ? node->content :
                            (node->value ? node->value : "");
        if (strlen(txt) >= sizeof(esc)) {
            memcpy(esc, txt, sizeof(esc) - 1);
            esc[sizeof(esc) - 1] = '\0';
        } else {
            xml_escape(esc, sizeof(esc), &eo, txt);
        }
        if (off + strlen(esc) + 1 >= buflen) return -1;
        memcpy(buf + off, esc, strlen(esc)); off += (unsigned int)strlen(esc);
    }
    return (int)off;
}

int mxml_write_node(mxml_node_t *node, const char *pad, unsigned int depth,
                    unsigned int flags, char *buf, unsigned int buflen)
{
    if (!node || !buf || buflen == 0) return -1;
    buf[0] = '\0';
    int r = write_node_recursive(node, pad ? pad : "", depth, flags, buf, buflen, 0);
    if (r < 0) { buf[0] = '\0'; return -1; }
    return r;
}

/* 输出到文件（vp 可以是 FILE*） */
int mxml_save(mxml_node_t *root, void *fp)
{
    if (!root || !fp) return -1;
    char tmp[16384];
    int n = mxml_write_node(root, "  ", 0, 1, tmp, (unsigned int)sizeof(tmp));
    if (n < 0) return -1;
    FILE *f = (FILE *)fp;
    size_t w = fwrite(tmp, 1, (size_t)n, f);
    return (int)w;
}

/* ---- XML 实体 ---- */

typedef struct { const char *entity; const char *value; } xml_entity_map_t;

static const xml_entity_map_t g_xml_entities[] = {
    {"amp",  "&"},
    {"lt",   "<"},
    {"gt",   ">"},
    {"quot", "\""},
    {"apos", "'"},
    {NULL,   NULL}
};

/* 查找实体表，返回替换后的字符串（静态常量） */
const char *mxml_get_entity(const char *value)
{
    if (!value || value[0] != '&') return value;
    /* 找分号 */
    const char *semi = strchr(value, ';');
    if (!semi) return value;
    size_t len = (size_t)(semi - value - 1); /* 去掉 & 和 ; */
    for (int i = 0; g_xml_entities[i].entity; i++) {
        if (strlen(g_xml_entities[i].entity) == len &&
            strncmp(g_xml_entities[i].entity, value + 1, len) == 0) {
            return g_xml_entities[i].value;
        }
    }
    return value;
}

/* 反解实体（解码 &amp; 等） */
int mxml_unescape(const char *in, char *out, unsigned int outsz)
{
    if (!in || !out || outsz == 0) return -1;
    unsigned int o = 0;
    while (*in && o + 1 < outsz) {
        if (*in == '&' && in[1]) {
            const char *semi = strchr(in, ';');
            if (semi && (semi - in) <= 8) {
                size_t len = (size_t)(semi - in - 1);
                for (int i = 0; g_xml_entities[i].entity; i++) {
                    if (strlen(g_xml_entities[i].entity) == len &&
                        strncmp(g_xml_entities[i].entity, in + 1, len) == 0) {
                        out[o++] = *g_xml_entities[i].value;
                        in = semi + 1;
                        goto next;
                    }
                }
                /* &#nn; / &#xhh; 数字实体 */
                if (in[1] == '#') {
                    unsigned int num = 0;
                    if (in[2] == 'x') {
                        for (const char *p = in + 3; p < semi &&
                             ((p[0] >= '0' && p[0] <= '9') ||
                              (p[0] >= 'a' && p[0] <= 'f') ||
                              (p[0] >= 'A' && p[0] <= 'F')); p++) {
                            num = num * 16 + (unsigned int)((p[0] <= '9') ?
                                (p[0] - '0') : (p[0] - 'a' + 10));
                        }
                    } else {
                        for (const char *p = in + 2; p < semi &&
                             p[0] >= '0' && p[0] <= '9'; p++) {
                            num = num * 10 + (unsigned int)(p[0] - '0');
                        }
                    }
                    if (o + 1 < outsz) { out[o++] = (char)(num & 0xFF); in = semi + 1; goto next; }
                }
            }
        }
        out[o++] = *in++;
next:;
    }
    out[o] = '\0';
    return (int)o;
}

/* ---- 索引 ---- */

static void index_collect(mxml_node_t *node, mxml_index_t *idx)
{
    if (!node || !idx) return;
    if (node->type == MXML_ELEMENT) {
        const char *v = mxml_get_attr(node, idx->key);
        if (v) {
            if (idx->count >= idx->capacity) {
                idx->capacity = idx->capacity ? idx->capacity * 2 : 16;
                idx->nodes = realloc(idx->nodes,
                    idx->capacity * sizeof(mxml_node_t *));
            }
            if (idx->nodes) idx->nodes[idx->count++] = node;
        }
        mxml_node_t *c = node->child;
        while (c) { index_collect(c, idx); c = c->next; }
    }
}

mxml_index_t *mxmlIndexNew(mxml_node_t *root, const char *name)
{
    if (!root || !name) return NULL;
    mxml_index_t *idx = calloc(1, sizeof(mxml_index_t));
    if (!idx) return NULL;
    idx->key = strdup(name);
    index_collect(root, idx);
    return idx;
}

mxml_node_t *mxmlIndexFind(mxml_index_t *idx, const char *value)
{
    if (!idx || !value) return NULL;
    for (unsigned int i = 0; i < idx->count; i++) {
        const char *v = mxml_get_attr(idx->nodes[i], idx->key);
        if (v && strcmp(v, value) == 0) return idx->nodes[i];
    }
    return NULL;
}

void mxmlIndexDelete(mxml_index_t *idx)
{
    if (!idx) return;
    free(idx->nodes);
    free(idx->key);
    free(idx);
}

/* ---- getc 系列（原厂 mxml_fd_getc / mxml_file_getc / mxml_string_getc） ---- */

typedef struct { int fd; } fd_ctx_t;
typedef struct { FILE *f; } file_ctx_t;
typedef struct { const char *s; size_t pos; size_t len; } str_ctx_t;

int mxml_fd_getc(void *cookie)
{
    (void)cookie; /* 需要平台 fd 层支持，此处返回 EOF 保底 */
    return -1;
}

int mxml_file_getc(void *cookie)
{
    if (!cookie) return -1;
    file_ctx_t *fc = (file_ctx_t *)cookie;
    if (!fc || !fc->f) return -1;
    int c = fgetc(fc->f);
    return c;
}

int mxml_string_getc(void *cookie)
{
    if (!cookie) return -1;
    str_ctx_t *sc = (str_ctx_t *)cookie;
    if (!sc || !sc->s) return -1;
    if (sc->pos >= sc->len) return -1;
    return (unsigned char)sc->s[sc->pos++];
}

/* ============================================================
 * mxml_add_char — 追加字符到节点文本内容（对齐原厂 420B）
 * ============================================================
 * 语义：
 *   - 若 node 为 NULL 或 type != MXML_ELEMENT 且 type != MXML_TEXT，返回 NULL
 *   - 若遇到 '\0' 直接终止（原厂行为）
 *   - 追加到 node->content，按需扩容
 *   - 返回 node（链式调用）
 */
mxml_node_t *mxml_add_char(mxml_node_t *node, int ch)
{
    if (!node) return NULL;
    if (ch == '\0') return node;
    if (node->type != MXML_ELEMENT && node->type != MXML_TEXT) return node;

    /* 每次调用重新分配（简单可靠，原厂 mxml_add_char 内部也是 realloc） */
    unsigned int new_len = node->content_len + 1;
    unsigned int cap = new_len + 1; /* 留 '\0' */
    if (cap < 64) cap = 64;

    char *newbuf = (char *)realloc(node->content, cap);
    if (!newbuf) return NULL;
    node->content = newbuf;

    node->content[node->content_len] = (char)ch;
    node->content_len = new_len;
    node->content[node->content_len] = '\0';

    /* 同步 value */
    if (!node->value) {
        node->value = strdup(node->content);
    }
    return node;
}

/* ============================================================
 * mxml 扩展 API（对齐原厂 102 符号，追加 35 个函数）
 * ============================================================ */

/* mxml_get_indent — 获取缩进设置（已实现于 Part 1） */

/* mxml_get_child_count — 获取子节点数量 */
unsigned int mxml_get_child_count(const mxml_node_t *node)
{
    if (!node) return 0;
    unsigned int count = 0;
    mxml_node_t *child = node->first_child;
    while (child) {
        count++;
        child = child->next_sibling;
    }
    return count;
}

/* mxml_get_num_children — 同 mxml_get_child_count */
unsigned int mxml_get_num_children(const mxml_node_t *node)
{
    return mxml_get_child_count(node);
}

/* mxml_get_child — 按索引获取子节点 */
mxml_node_t *mxml_get_child(const mxml_node_t *node, unsigned int index)
{
    if (!node) return NULL;
    mxml_node_t *child = node->first_child;
    while (child && index > 0) {
        child = child->next_sibling;
        index--;
    }
    return child;
}

/* mxml_get_parent — 获取父节点 */
const mxml_node_t *mxml_get_parent(const mxml_node_t *node)
{
    if (!node) return NULL;
    return node->parent;
}

/* mxml_get_prev_sibling — 获取前一个兄弟节点 */
const mxml_node_t *mxml_get_prev_sibling(const mxml_node_t *node)
{
    if (!node) return NULL;
    return node->prev_sibling;
}

/* mxml_get_next_sibling — 获取后一个兄弟节点（别名） */
const mxml_node_t *mxml_get_next_sibling(const mxml_node_t *node)
{
    if (!node) return NULL;
    return node->next_sibling;
}

/* mxml_set_content — 设置节点文本内容 */
void mxml_set_content(mxml_node_t *node, const char *content)
{
    if (!node || !content) return;
    if (node->content) free(node->content);
    node->content = strdup(content);
    node->content_len = strlen(content);
    if (!node->value) node->value = strdup(content);
}

/* mxml_set_type — 设置节点类型 */
void mxml_set_type(mxml_node_t *node, mxml_type_t type)
{
    if (node) node->type = type;
}

/* mxml_get_type — 获取节点类型 */
mxml_type_t mxml_get_type(const mxml_node_t *node)
{
    if (!node) return MXML_NONE;
    return node->type;
}

/* mxml_set_data — 设置节点数据 */
void mxml_set_data(mxml_node_t *node, void *data)
{
    if (node) node->data = data;
}

/* mxml_get_data — 获取节点数据 */
void *mxml_get_data(const mxml_node_t *node)
{
    if (!node) return NULL;
    return node->data;
}

/* mxml_set_value — 设置节点值 */
void mxml_set_value(mxml_node_t *node, const char *value)
{
    if (!node) return;
    if (node->value) free(node->value);
    node->value = value ? strdup(value) : NULL;
}

/* mxml_get_value — 获取节点值 */
const char *mxml_get_value(const mxml_node_t *node)
{
    if (!node) return NULL;
    return node->value;
}

/* mxml_release_data — 释放节点数据 */
void mxml_release_data(mxml_node_t *node)
{
    if (!node) return;
    node->data = NULL;
}

/* mxml_get_num_attrs — 获取属性数量 */
unsigned int mxml_get_num_attrs(const mxml_node_t *node)
{
    if (!node) return 0;
    return node->num_attrs;
}

/* mxml_set_num_attrs — 设置属性数量 */
void mxml_set_num_attrs(mxml_node_t *node, unsigned int count)
{
    if (node) node->num_attrs = count;
}

/* mxml_get_attr_name — 按索引获取属性名 */
const char *mxml_get_attr_name(const mxml_node_t *node, unsigned int index)
{
    if (!node || index >= node->num_attrs) return NULL;
    return node->attrs[index].name;
}

/* mxml_get_attr_value — 按索引获取属性值 */
const char *mxml_get_attr_value(const mxml_node_t *node, unsigned int index)
{
    if (!node || index >= node->num_attrs) return NULL;
    return node->attrs[index].value;
}

/* mxml_add_attr — 添加属性 */
void mxml_add_attr(mxml_node_t *node, const char *name, const char *value)
{
    if (!node || !name) return;
    if (node->num_attrs >= MXML_MAX_ATTRS) return;
    node->attrs[node->num_attrs].name = strdup(name);
    node->attrs[node->num_attrs].value = value ? strdup(value) : NULL;
    node->num_attrs++;
}

/* mxml_delete_attr — 删除属性 */
void mxml_delete_attr(mxml_node_t *node, unsigned int index)
{
    if (!node || index >= node->num_attrs) return;
    if (node->attrs[index].name) free(node->attrs[index].name);
    if (node->attrs[index].value) free(node->attrs[index].value);
    /* 移动后续属性 */
    for (unsigned int i = index; i < node->num_attrs - 1; i++) {
        node->attrs[i] = node->attrs[i + 1];
    }
    node->num_attrs--;
}

/* mxml_release_attr — 释放属性 */
void mxml_release_attr(mxml_node_t *node, unsigned int index)
{
    mxml_delete_attr(node, index);
}

/* mxml_add_child — 添加子节点 */
mxml_node_t *mxml_add_child(mxml_node_t *parent, mxml_node_t *child)
{
    if (!parent || !child) return NULL;
    if (parent->first_child == NULL) {
        parent->first_child = child;
        parent->last_child = child;
    } else {
        parent->last_child->next_sibling = child;
        child->prev_sibling = parent->last_child;
        parent->last_child = child;
    }
    child->parent = parent;
    return child;
}

/* mxml_add_sibling — 添加兄弟节点 */
mxml_node_t *mxml_add_sibling(mxml_node_t *node, mxml_node_t *sibling)
{
    if (!node || !sibling) return NULL;
    sibling->next_sibling = node->next_sibling;
    sibling->prev_sibling = node;
    sibling->parent = node->parent;
    node->next_sibling = sibling;
    if (sibling->next_sibling) {
        sibling->next_sibling->prev_sibling = sibling;
    }
    return sibling;
}

/* mxml_remove_child — 移除子节点 */
void mxml_remove_child(mxml_node_t *parent, mxml_node_t *child)
{
    if (!parent || !child) return;
    if (child->prev_sibling) {
        child->prev_sibling->next_sibling = child->next_sibling;
    } else {
        parent->first_child = child->next_sibling;
    }
    if (child->next_sibling) {
        child->next_sibling->prev_sibling = child->prev_sibling;
    } else {
        parent->last_child = child->prev_sibling;
    }
    child->parent = NULL;
    child->prev_sibling = NULL;
    child->next_sibling = NULL;
}

/* mxml_remove_sibling — 移除兄弟节点 */
void mxml_remove_sibling(mxml_node_t *node)
{
    if (!node) return;
    mxml_remove_child(node->parent, node);
}

/* mxml_release_child — 释放子节点 */
mxml_node_t *mxml_release_child(mxml_node_t *parent, mxml_node_t *child)
{
    mxml_node_t *next = child->next_sibling;
    mxml_remove_child(parent, child);
    mxml_free(child);
    return next;
}

/* mxml_release_sibling — 释放兄弟节点 */
mxml_node_t *mxml_release_sibling(mxml_node_t *node)
{
    mxml_node_t *next = node->next_sibling;
    mxml_remove_sibling(node);
    mxml_free(node);
    return next;
}

/* mxml_new_text_node — 创建文本节点 */
mxml_node_t *mxml_new_text_node(mxml_node_t *parent, const char *text)
{
    mxml_node_t *node = mxml_new_node(parent, MXML_TEXT, text);
    return node;
}

/* mxml_new_element — 创建元素节点 */
mxml_node_t *mxml_new_element(mxml_node_t *parent, const char *name,
                              const char *value, const char **attrs)
{
    mxml_node_t *node = mxml_new_node(parent, MXML_ELEMENT, name);
    if (node && value) mxml_set_attr(node, "value", value);
    if (node && attrs) {
        unsigned int i = 0;
        while (attrs[i] && i < MXML_MAX_ATTRS) {
            /* 简单处理：attrs 格式为 "name=value" */
            char *name_val = strdup(attrs[i]);
            if (name_val) {
                char *eq = strchr(name_val, '=');
                if (eq) {
                    *eq = '\0';
                    mxml_set_attr(node, name_val, eq + 1);
                }
                free(name_val);
            }
            i += 2;
        }
    }
    return node;
}

/* mxml_new_cdata — 创建 CDATA 节点 */
mxml_node_t *mxml_new_cdata(mxml_node_t *parent, const char *text)
{
    mxml_node_t *node = mxml_new_node(parent, MXML_CDATA, text);
    return node;
}

/* mxml_new_comment — 创建注释节点 */
mxml_node_t *mxml_new_comment(mxml_node_t *parent, const char *text)
{
    mxml_node_t *node = mxml_new_node(parent, MXML_COMMENT, text);
    return node;
}

/* mxml_new_decl — 创建声明节点 */
mxml_node_t *mxml_new_decl(mxml_node_t *parent, const char *version,
                           const char *encoding)
{
    mxml_node_t *node = mxml_new_node(parent, MXML_DECL, "xml");
    if (node && version) mxml_set_attr(node, "version", version);
    if (node && encoding) mxml_set_attr(node, "encoding", encoding);
    return node;
}

/* mxml_new_doc — 创建文档节点 */
mxml_node_t *mxml_new_doc(const char *version)
{
    mxml_node_t *doc = mxml_new_node(NULL, MXML_DOCUMENT, "document");
    if (doc && version) {
        mxml_node_t *decl = mxml_new_decl(doc, version, "UTF-8");
        (void)decl;
    }
    return doc;
}

/* mxml_new_pi — 创建处理指令节点 */
mxml_node_t *mxml_new_pi(mxml_node_t *parent, const char *target,
                         const char *data)
{
    mxml_node_t *node = mxml_new_node(parent, MXML_PI, target);
    if (node && data) mxml_set_attr(node, "data", data);
    return node;
}

/* mxml_skip_whitespace — 跳过空白（公开版本） */
void mxml_skip_whitespace(mxml_parser_t *parser)
{
    skip_whitespace(parser);
}

/* mxml_read_string — 读取字符串（公开版本） */
char *mxml_read_string(mxml_parser_t *parser, const char *delim)
{
    return read_string(parser, delim);
}

/* mxml_parse_attrs — 解析属性（公开版本） */
void mxml_parse_attrs(mxml_parser_t *parser, mxml_node_t *node)
{
    /* 属性解析在 parse_element 内部完成，此处为兼容接口 */
    (void)parser;
    (void)node;
}

/* mxml_parse_element — 解析元素（公开版本） */
mxml_node_t *mxml_parse_element(mxml_parser_t *parser)
{
    return parse_element(parser);
}

/* mxml_release_node — 释放节点（别名） */
void mxml_release_node(mxml_node_t *node)
{
    mxml_free(node);
}

/* mxml_get_indent — 设置缩进（已实现） */

/* mxml_set_char_data — 设置字符数据 */
void mxml_set_char_data(mxml_node_t *node, const char *data, unsigned int len)
{
    if (!node || !data) return;
    if (node->content) free(node->content);
    node->content = malloc(len + 1);
    if (node->content) {
        memcpy(node->content, data, len);
        node->content[len] = '\0';
        node->content_len = len;
    }
}

/* mxml_get_char_data — 获取字符数据 */
const char *mxml_get_char_data(const mxml_node_t *node)
{
    if (!node) return NULL;
    return node->content;
}

/* mxml_get_char_len — 获取字符数据长度 */
unsigned int mxml_get_char_len(const mxml_node_t *node)
{
    if (!node) return 0;
    return node->content_len;
}

/* ============================================================
 * 扩展：mxml 完整 API（对齐原厂 102 符号）
 */
