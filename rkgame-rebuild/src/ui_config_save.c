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
