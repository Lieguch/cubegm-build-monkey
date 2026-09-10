/* ============================================================
 * ui_config_save.c — 配置写回（config_save / SaveSetting）
 * ============================================================
 *
 * 原厂 SaveSetting 会将 g_cfg 写回 setting.xml。
 * 使用标准 XML 格式输出，与 mui_LoadSetting 解析格式对齐。
 * ============================================================ */

#include "rkgame.h"
#include "ui_config.h"
#include "debug.h"

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <stdlib.h>

/* 转义 XML 特殊字符 */
static void xml_escape(FILE *fp, const char *s)
{
    if (!s) { fputs("", fp); return; }
    for (const char *p = s; *p; p++) {
        switch (*p) {
            case '&':  fputs("&amp;", fp); break;
            case '<':  fputs("&lt;",  fp); break;
            case '>':  fputs("&gt;",  fp); break;
            case '"':  fputs("&quot;",fp); break;
            case '\'': fputs("&apos;",fp); break;
            default:   fputc(*p, fp); break;
        }
    }
}

/* 写回 setting.xml */
int config_save_setting(const char *path)
{
    if (!path) return -1;
    FILE *fp = fopen(path, "w");
    if (!fp) {
        RKLOG_E("config_save_setting: cannot open %s for write", path);
        return -1;
    }

    fprintf(fp, "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n");
    fprintf(fp, "<setting>\n");
    fprintf(fp, "  <config language=\"%d\" volume=\"%d\"/>\n",
            g_cfg.m_ui, g_cfg.volume);
    fprintf(fp, "  <defaultlanguage value=\"%d\"/>\n", g_cfg.defaultlanguage);
    fprintf(fp, "  <displayfps value=\"%d\"/>\n", g_cfg.displayfps);
    fprintf(fp, "  <displaythread value=\"%d\"/>\n", g_cfg.displaythread);
    fprintf(fp, "  <softrotation value=\"%d\"/>\n", g_cfg.soft_rotation);
    if (g_cfg.logfile[0]) {
        fprintf(fp, "  <logfile value=\"");
        xml_escape(fp, g_cfg.logfile);
        fprintf(fp, "\"/>\n");
    }
    if (save_directory[0]) {
        fprintf(fp, "  <save_directory directory=\"");
        xml_escape(fp, save_directory);
        fprintf(fp, "\"/>\n");
    }
    if (g_cfg.filebrowser[0]) {
        fprintf(fp, "  <filebrowser value=\"");
        xml_escape(fp, g_cfg.filebrowser);
        fprintf(fp, "\"/>\n");
    }
    if (g_cfg.music_file[0]) {
        fprintf(fp, "  <music>\n");
        fprintf(fp, "    <bgm file=\"");
        xml_escape(fp, g_cfg.music_file);
        fprintf(fp, "\"/>\n");
        fprintf(fp, "  </music>\n");
    }
    if (g_cfg.effect0_file[0] || g_cfg.effect1_file[0]) {
        fprintf(fp, "  <sound>\n");
        if (g_cfg.effect0_file[0]) {
            fprintf(fp, "    <effect0 file=\"");
            xml_escape(fp, g_cfg.effect0_file);
            fprintf(fp, "\"/>\n");
        }
        if (g_cfg.effect1_file[0]) {
            fprintf(fp, "    <effect1 file=\"");
            xml_escape(fp, g_cfg.effect1_file);
            fprintf(fp, "\"/>\n");
        }
        fprintf(fp, "  </sound>\n");
    }
    if (g_cfg.autorun_path[0]) {
        fprintf(fp, "  <autorun file=\"");
        xml_escape(fp, g_cfg.autorun_path);
        fprintf(fp, "\"");
        if (g_cfg.autorun_driver[0]) {
            fprintf(fp, " driver=\"");
            xml_escape(fp, g_cfg.autorun_driver);
            fprintf(fp, "\"");
        }
        fprintf(fp, "/>\n");
    }
    fprintf(fp, "</setting>\n");
    fclose(fp);
    RKLOG_I("config_save_setting: wrote %s", path);
    return 0;
}

/* 别名：SaveSetting 供 main.c 调用 */
int SaveSetting(void)
{
    char path[512];
    snprintf(path, sizeof(path), "%ssetting.xml", work_path);
    return config_save_setting(path);
}

/* ============================================================
 * SaveLanguageSetting — 原厂 1:1 language 写回（<ui> 候选块保持）
 * ------------------------------------------------------------
 * 对齐 mui_setting @ 0x2b2b4 L550-575 的语义：只改
 * <config ... language="N" ...> 的 language 属性值，**不触碰**
 * 9 个 <ui> 候选块与 <sound> 等其它节（区别于 config_save_setting
 * 的全量重写，后者会丢失 <ui> 条目）。
 *
 * 实现用「原地字符串替换」而非 mxml 重新序列化：
 *   - device 的 setting.xml 是**扁平多顶层**结构（<autorun/><savestatehotkey/>
 *     <config/><ui>×9 <sound>），没有单一 root 元素。lib/mxml 的
 *     mxml_load_data 只解析第一个顶层元素，会把 <config> 之后的 <ui> 全部
 *     丢弃 → mxml 重序列化会**抹掉 9 个 <ui> 候选块**（致命）。
 *   - 因此改为读全文 → 定位 <config> 节内的 language="X" → 替换数值
 *     → 写回 + fsync。其它字节原样保留。与 select_ui_zip 的 strstr 解析
 *     保持同一格式假设，读写对称。
 * 返回 0 成功，-1 失败。language_index 值域 0..8（对齐 number[]）。
 * ============================================================ */
int SaveLanguageSetting(int language_index)
{
    char path[512];
    snprintf(path, sizeof(path), "%ssetting.xml", work_path);

    /* 1) 读全文 */
    FILE *rfp = fopen(path, "rb");
    if (!rfp) {
        RKLOG_E("SaveLanguageSetting: cannot open %s for read", path);
        return -1;
    }
    fseek(rfp, 0, SEEK_END);
    long fsz = ftell(rfp);
    fseek(rfp, 0, SEEK_SET);
    if (fsz <= 0 || fsz > 256 * 1024) {
        fclose(rfp);
        RKLOG_E("SaveLanguageSetting: bad size %ld", fsz);
        return -1;
    }
    char *buf = (char *)malloc((size_t)fsz + 1);
    if (!buf) { fclose(rfp); return -1; }
    size_t nread = fread(buf, 1, (size_t)fsz, rfp);
    fclose(rfp);
    buf[nread] = '\0';

    /* 2) 定位 <config ...> 节内的 language="X" */
    const char *cfg = strstr(buf, "<config");
    if (!cfg) {
        free(buf);
        RKLOG_E("SaveLanguageSetting: no <config> in setting.xml");
        return -1;
    }
    const char *lang = strstr(cfg, "language=");
    if (!lang) {
        free(buf);
        RKLOG_E("SaveLanguageSetting: no language= attr in <config>");
        return -1;
    }
    lang += strlen("language=");

    /* 定位数值区（引号内），把旧值整段替换为 new 值 */
    char *val_start;
    if (*lang == '"') {
        val_start = lang + 1;                 /* 跳过开引号 */
    } else {
        val_start = lang;                     /* 无引号形式 */
    }
    /* 找值结束：引号或空白或 > 或 / */
    char *end_ptr = val_start;
    while (*end_ptr && *end_ptr != '"' && *end_ptr != ' ' &&
           *end_ptr != '\t' && *end_ptr != '>' && *end_ptr != '/') {
        end_ptr++;
    }
    int old_len = (int)(end_ptr - val_start);

    char newval[8];
    int nval_len = snprintf(newval, sizeof(newval), "%d", language_index);

    /* 3) 原地替换 [val_start, val_start+old_len) → newval
       language 值域 0..8（1 位数），位数不变 → old_len==nval_len==1，
       直接 overwrite，无移位。若未来扩展到 2 位数则需 memmove。 */
    if (old_len == nval_len) {
        memcpy(val_start, newval, (size_t)nval_len);
    } else {
        /* 位数变化（扩展预留）：尾部整体移动 delta 字节 */
        int delta = nval_len - old_len;
        size_t tail_from = (size_t)(end_ptr - buf);
        size_t tail_len = nread - tail_from;
        if (delta > 0) {
            memmove(end_ptr + nval_len, end_ptr, tail_len);
        } else {
            memmove(end_ptr + delta, end_ptr, tail_len);
        }
        memcpy(val_start, newval, (size_t)nval_len);
    }

    /* 4) 写回 + fsync */
    FILE *wfp = fopen(path, "w");
    if (!wfp) {
        free(buf);
        RKLOG_E("SaveLanguageSetting: cannot open %s for write", path);
        return -1;
    }
    /* 长度可能因位数变化而改，用 strlen 重新计算（buf 已 NUL 终止） */
    fwrite(buf, 1, strlen(buf), wfp);
    fflush(wfp);
    fsync(fileno(wfp));
    fclose(wfp);
    free(buf);

    RKLOG_I("SaveLanguageSetting: <config language=\"%d\"> written (ui_list kept)",
            language_index);
    return 0;
}
