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
        if (child->type == MXML_ELEMENT) {
            if (strcmp(child->value, element) == 0) {
                if (!value || strcmp(mxml_get_attr(child, value ? value : ""), value ? value : "") == 0) {
                    if (count == index) {
                        return child;
                    }
                    count++;
                }
            }
            
            /* 递归查找 */
            mxml_node_t *found = mxml_find_element(child, element, value, index);
            if (found) return found;
        }
        
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
