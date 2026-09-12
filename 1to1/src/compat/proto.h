/* proto.h — 函数原型（反编译签名行） */
#ifndef RK_PROTO_H
#define RK_PROTO_H
#include "ghidra_compat.h"
#include "globals.h"

extern gh_u4 main(); /* K&R: 参数不可信/不可解析 */
extern void RARCH_LOG_V(); /* K&R: 参数不可信/不可解析 */
extern void RARCH_LOG(); /* K&R: 参数不可信/不可解析 */
extern void GetConfig(); /* K&R: 参数不可信/不可解析 */
extern int get_executable_path(char *param_1,char *param_2,size_t param_3);
extern void dispmeninfo(); /* K&R: 参数不可信/不可解析 */
extern void outputxy1(gh_byte *param_1);
extern void spi_printf(char *param_1, ...); /* 原厂为变参（AAPCS32 va_start 序言） */
extern gh_u4 * ShareMemCreat(void); /* 对齐 Ghidra 定义 FUN_0000a774 */
extern gh_u4 ShareMemClose(); /* K&R: 参数不可信/不可解析 */
extern void xintiao(); /* K&R: 参数不可信/不可解析 */
extern void XintiaoThread(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 UpdateROMProc(int param_1,int param_2);
extern void DateToTmuDate(gh_uint param_1);
extern void UpdateROM(char *param_1);
extern void TestUSBJoy(); /* K&R: 参数不可信/不可解析 */
extern gh_longlong GetTick(void); /* 原厂返回 64 位微秒；Ghidra 漏判返回值 */
extern void WaitNMI(); /* K&R: 参数不可信/不可解析 */
extern void TestRun(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 TestLibz0(); /* K&R: 参数不可信/不可解析 */
extern void TestLibz1(); /* K&R: 参数不可信/不可解析 */
extern void * sunxi_gpio_init(void); /* 对齐 Ghidra 定义 FUN_0000ba1c */
extern gh_u4 sunxi_gpio_set_cfgpin(int param_1,int param_2);
extern gh_uint sunxi_gpio_get_cfgpin(gh_uint param_1);
extern gh_u4 sunxi_gpio_output(); /* K&R: 参数不可信/不可解析 */
extern gh_uint sunxi_gpio_input(gh_uint param_1);
extern void sunxi_gpio_cleanup(); /* K&R: 参数不可信/不可解析 */
extern char * get_from_line(char *param_1,int param_2); /* 对齐 Ghidra 定义 FUN_0000bf9c */
extern gh_u4 GetInputInfo(char *param_1,char *param_2);
extern gh_uint ReadUSBJoy(int param_1);
extern void InitMDJoystick(); /* K&R: 参数不可信/不可解析 */
extern void ReadPS2JS(gh_uint param_1,gh_byte *param_2,gh_byte *param_3);
extern void ReadJoystickProc(); /* K&R: 参数不可信/不可解析 */
extern void processvblank(); /* K&R: 参数不可信/不可解析 */
extern void ReadJoystickThread(); /* K&R: 参数不可信/不可解析 */
extern void timer_thread(); /* K&R: 参数不可信/不可解析 */
extern void SetBacklight(int param_1);
extern void InitIOSignal(); /* K&R: 参数不可信/不可解析 */
extern void OutputIOSignal(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 ReadJoystick(); /* K&R: 参数不可信/不可解析 */
extern void osDelay(int param_1);
extern void SPI_WW(gh_uint param_1);
extern gh_uint SPI_RR(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 SPI_Read(gh_u4 param_1);
extern void SPI_Read_BUF(gh_u4 param_1,int param_2,gh_u1 *param_3);
extern void SPI_Write_BUF(gh_u4 param_1,int param_2,gh_u1 *param_3);
extern void SPI_Write(gh_u4 param_1,gh_u4 param_2);
extern void RxMode(); /* K&R: 参数不可信/不可解析 */
extern void TxMode(); /* K&R: 参数不可信/不可解析 */
extern int getticks(); /* K&R: 参数不可信/不可解析 */
extern void RF_Joystick_timer_isr(); /* K&R: 参数不可信/不可解析 */
extern void InitRFJoystick(); /* K&R: 参数不可信/不可解析 */
extern void InitJoystick(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 GetDecodeData(); /* K&R: 参数不可信/不可解析 */
extern void InitDecode(); /* K&R: 参数不可信/不可解析 */
extern void ReInitDecode(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 ScaleDisplayThread(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 run_process_constprop_0(char *param_1);
extern gh_u4 InitDisplay(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 dispFlip(void *param_1,gh_u4 param_2,gh_u4 param_3,gh_u4 param_4);
extern void video_driver_set_rotation(gh_u4 param_1);
extern void video_driver_set_colormode(); /* K&R: 参数不可信/不可解析 */
extern void DeinitDisplay(); /* K&R: 参数不可信/不可解析 */
extern void InitSound(); /* K&R: 参数不可信/不可解析 */
extern void DeinitSound(); /* K&R: 参数不可信/不可解析 */
extern void PlaySound(); /* K&R: 参数不可信/不可解析 */
extern gh_uint ucrc32(gh_uint param_1,gh_byte *param_2,gh_uint param_3);
extern gh_u4 * OpenZipU(void *param_1,gh_uint param_2,gh_uint param_3); /* 对齐 Ghidra 定义 FUN_00012cd0 */
extern gh_u4 GetZipItemA(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 FindZipItemA(gh_u4 *param_1,char *param_2,gh_uchar param_3,int *param_4,void *param_5);
extern gh_u4 UnzipItem(gh_u4 *param_1,int param_2,void *param_3,gh_uint param_4,gh_uint param_5);
extern gh_u4 CloseZipU(gh_u4 *param_1);
extern void DrawSelectBar(int *param_1);
extern void mui_blockcopy(int *param_1,int *param_2);
extern void UnDrawSelectBar(int *param_1,int param_2,int param_3);
extern void mui_DispBlock(); /* K&R: 参数不可信/不可解析 */
extern void mui_UnDispBlock(); /* K&R: 参数不可信/不可解析 */
extern void mui_Undisplay(int param_1,int param_2,int param_3,int param_4);
extern void mui_extract_basepath(char *param_1,char *param_2,int param_3);
extern void mui_extract_basename(char *param_1,char *param_2,int param_3);
extern void mui_DisplayThumbnail(); /* K&R: 参数不可信/不可解析 */
extern long buttontoi(char *param_1);
extern int code_convert_constprop_22(); /* K&R: 参数不可信/不可解析 */
extern gh_byte * strupr(); /* K&R：调用点 0 参 */
extern gh_u4 FilePreEmu(); /* K&R: 参数不可信/不可解析 */
extern gh_u1 * GetWorkPath(void); /* 对齐 Ghidra 定义 FUN_000171dc */
extern void mui_LoadSetting(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 mui_LoadUIResource(gh_u4 **param_1,char *param_2);
extern void shoucang(char *param_1);
extern gh_u4 IsShoucang(char *param_1);
extern int mui_do_file_list(int param_1,gh_byte *param_2);
extern int mui_type_file_list(int param_1,gh_byte *param_2);
extern int mui_search_file_list(int param_1,int param_2);
extern int GetTicks(); /* K&R: 参数不可信/不可解析 */
extern void mui_DisplayThumbnailThread(); /* K&R: 参数不可信/不可解析 */
extern void mui_WaitNMI(); /* K&R: 参数不可信/不可解析 */
extern void stbtt_GetFontVMetrics(); /* K&R: 参数不可信/不可解析 */
extern float stbtt_ScaleForPixelHeight(float param_1,void *param_2);
extern int mui_outputxy_length_isra_19(int param_1,int param_2,gh_byte *param_3);
extern int mui_outputxy_t(gh_u1 *param_1,int param_2,int param_3,int param_4,gh_uint param_5,gh_byte *param_6);
extern void mui_DisplayGameSum(); /* K&R: 参数不可信/不可解析 */
extern void mui_DisplayLine_t(int param_1,int param_2,int param_3);
extern void mui_DisplayInputBuffer(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 stbtt_InitFont(void *param_1,void *param_2,gh_u4 param_3); /* font[124] 与 fontbuffer 均为缓冲指针 */
extern void mui_InitFont(); /* K&R: 参数不可信/不可解析 */
extern char * strtrimr(); /* K&R：strtrim 内以 0 参尾调用 */
extern gh_byte * strtriml(); /* K&R：strtrim 内以 0 参尾调用 */
extern char * strtrim(); /* 原厂为 strtriml→strtrimr 尾调用，返回指针（调用点用返回值） */
extern char * get_item_from_line(char *param_1,char *param_2);
extern int get_items_from_file(char *param_1,char *param_2);
extern int get_items_from_zipfile(char *param_1,char *param_2); /* param_1 用于 %s；param_2 参与指针算术并传 get_item_from_line */
extern char * get_value_from_items(char *param_1,char *param_2,char *param_3,int param_4); /* 对齐 Ghidra 定义 FUN_0001f514 */
extern void mui_LoadConfig(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 gameType(void); /* 原厂返回位索引 uVar1；Ghidra 漏判返回值 */
extern void LoadMenuLog(); /* K&R: 参数不可信/不可解析 */
extern void SaveMenuLog(); /* K&R: 参数不可信/不可解析 */
extern gh_uint mui_ReadJoystick(); /* K&R: 参数不可信/不可解析 */
extern int dir_serial_list(); /* K&R: 参数不可信/不可解析 */
extern void outputblankxy(); /* K&R: 参数不可信/不可解析 */
extern void DisplayLine_list(gh_u4 param_1,int param_2,int param_3);
extern void DisplayPage_list(int param_1,gh_u4 param_2,int param_3);
extern char * myStrrstr(char *param_1,char *param_2); /* 对齐 Ghidra 定义 FUN_0002197c */
extern void EmuCore_Blank(); /* K&R: 参数不可信/不可解析 */
extern void EmuCore_Line(int param_1,int param_2,int param_3);
extern void EmuCore_list(int param_1,gh_u4 param_2,int param_3);
extern int SeletEmuCore(gh_byte *param_1); /* 调用点传 char[256]；体内作 mui_outputxy_t 的 gh_byte* 实参 */
extern gh_u4 GetFileCore(char *param_1);
extern gh_u4 ui_GetVolume(); /* K&R: 参数不可信/不可解析 */
extern void SoundClose(); /* K&R: 参数不可信/不可解析 */
extern void ui_deinit(); /* K&R: 参数不可信/不可解析 */
extern void SoundPlay(int param_1,int *param_2);
extern gh_u4 filelist_run_game(char *param_1);
extern gh_u4 mui_run_game(char *param_1);
extern void mui_menu(); /* K&R: 参数不可信/不可解析 */
extern void mui_type(); /* K&R: 参数不可信/不可解析 */
extern void mui_search(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 Mp3DecodeLoop(); /* K&R: 参数不可信/不可解析 */
extern void AudioProcess(); /* K&R: 参数不可信/不可解析 */
extern void mui_SoundplayThread(); /* K&R: 参数不可信/不可解析 */
extern void LoadDefaultState(); /* K&R: 参数不可信/不可解析 */
extern void SaveDefaultState(); /* K&R: 参数不可信/不可解析 */
extern void InitKeyMapping0fEmuType(); /* K&R: 参数不可信/不可解析 */
extern void SaveKeyMappingConfigFile(); /* K&R: 参数不可信/不可解析 */
extern void blockadaptive(int *param_1,int *param_2);
extern void popwindows(gh_u4 *param_1);
extern void popoffwindows(gh_u4 *param_1);
extern void mui_recent(); /* K&R: 参数不可信/不可解析 */
extern void mui_shoucang(); /* K&R: 参数不可信/不可解析 */
extern void blockcopy(int *param_1,int *param_2);
extern void draw_state_select(int param_1,int param_2,int param_3);
extern void progress(char *param_1,gh_u4 param_2);
extern void spi_memcpy(); /* K&R: 参数不可信/不可解析 */
extern void InitScr(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 GetJoystickConfig(void *param_1,gh_u4 param_2,gh_u4 param_3,gh_u4 param_4);
extern void JoystickTest(); /* K&R: 参数不可信/不可解析 */
extern void mui_setting(); /* K&R: 参数不可信/不可解析 */
extern void main_Menu(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 mui_joystick_setting(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 mui_video_setting(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 mui_load_state(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 mui_save_state(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 mui_game_exit(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 PauseMenu(); /* K&R: 参数不可信/不可解析 */
extern void joystick_poll(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 PlayFrame(gh_u4 param_1,gh_u4 param_2);
extern gh_u4 gpsp_unzip(gh_u4 param_1,char *param_2); /* 体内 RARCH_LOG %s 使用 param_2 */
extern void log_dummy(gh_uint param_1,gh_u4 param_2);
extern gh_bool joystick_input(gh_uint param_1,gh_u4 param_2,gh_u4 param_3,int param_4);
extern gh_u4 environment(int param_1,gh_uint *param_2);
extern void UIDebug(void *param_1,int param_2,gh_u4 param_3,gh_uint param_4);
extern void DrawFrame(gh_u2 *param_1,int param_2,int param_3,int param_4);
extern void rgb8888_to_rgb565(gh_ushort *param_1,int param_2,int param_3);
extern int GetCoreIndex(char *param_1);
extern char * GetFilenameExt(); /* K&R: 0/1 参调用点并存，返回类型按定义 char* */
extern void extract_basepath(char *param_1,char *param_2,int param_3);
extern void init_user_joy_key_mask(void *param_1,gh_u4 param_2);
extern void TurboKeyProcess(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 run_process(char *param_1,gh_code *param_2);
extern void RetroInitSound(); /* K&R: 参数不可信/不可解析 */
extern gh_bool Load_Proc1(char *param_1);
extern void Load_Proc2(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 Snes_Load(char *param_1,int param_2);
extern gh_u4 TGB_Load(char *param_1,int param_2);
extern gh_u4 prosystem_Load(char *param_1,int param_2);
extern gh_u4 stella_Load(char *param_1,int param_2);
extern gh_u4 PCSX_Load(char *param_1);
extern gh_u4 FBA_Load(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 Core_Load(char *param_1,char *param_2); /* 体内 sprintf("%s/cores/%s",...,param_2) → char* */
extern gh_u4 Gpsp_Load(char *param_1,int param_2);
extern gh_u4 run_game(); /* K&R: 参数不可信/不可解析 */
extern void autorun(char *param_1,char *param_2);
extern gh_u4 NES_Load(char *param_1,int param_2);
extern gh_u4 GBC_Load(char *param_1,int param_2);
extern gh_u4 VRT_Load(char *param_1,int param_2);
extern gh_u4 Pico_Load(char *param_1,int param_2);
extern gh_u4 retro_save_state(char *param_1);
extern gh_u4 retro_load_state(char *param_1);
extern void MP3FreeDecoder(); /* K&R: 参数不可信/不可解析 */
extern int MP3FindSyncWord(gh_byte *param_1,int param_2);
extern void MP3GetLastFrameInfo(int param_1,gh_u4 *param_2);
extern gh_u4 MP3GetNextFrameInfo(int param_1,gh_u4 *param_2,gh_u4 param_3); /* param_2 透传 MP3GetLastFrameInfo(gh_u4*) */
extern gh_u4 MP3Decode(int param_1,int *param_2,int *param_3,int param_4,int param_5);
extern void Convert_Stereo(gh_u2 *param_1);
extern void Convert_Mono(gh_u2 *param_1);
extern gh_u4 xmp3_UnpackFrameHeader(int *param_1,char *param_2);
extern void ClearBuffer(gh_u1 *param_1,int param_2);
extern gh_u4 mxmlElementGetAttr(gh_u4 param_1,char *param_2);
extern void mxmlElementSetAttr(gh_u4 param_1,char *param_2,gh_u4 param_3); /* node 以整型句柄传递；name/value 为字符串 */
extern gh_u4 mxmlLoadFile(); /* K&R: 参数不可信/不可解析 */
extern int mxmlSaveFile(); /* K&R: 参数不可信/不可解析 */
extern void mxmlDelete(); /* K&R: 参数不可信/不可解析 */
extern int mxmlFindElement(int param_1,int param_2,char *param_3,int param_4,char *param_5,int param_6);
extern gh_uint sfc_request(gh_uint *param_1,gh_uint param_2,gh_uint *param_3,gh_uint param_4);
extern int snor_wait_busy(int param_1);
extern void snor_write_en(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 spi_write(); /* K&R：调用点少参；返回 sfc_request/snor_wait_busy 结果 */
extern gh_u4 erase_sector(); /* K&R：调用点少参；原厂 r0 返回 sfc_request/snor_wait_busy 结果 */
extern gh_u4 spi_read(); /* K&R：调用点少参；返回 sfc_request 结果 */
extern void sflash_write_security_data(void *param_1,gh_u4 param_2);
extern void sflash_erase_security_data(gh_u4 param_1);
extern void sflash_read_security_data(void *param_1,gh_u4 param_2);
extern gh_u4 spi_driver_init(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 sfc_uninit(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 sfc_init(); /* K&R: 参数不可信/不可解析 */
extern gh_uint utf7_reset(int param_1,char *param_2,gh_uint param_3);
extern gh_bool normal_flushwc(int param_1,int *param_2);
extern gh_u4 hz_reset(int param_1,gh_u1 *param_2,gh_uint param_3);
extern void uc_to_mb_write_replacement(void *param_1,gh_uint param_2,int *param_3);
extern void wc_to_mb_write_replacement(void *param_1,gh_uint param_2,int *param_3);
extern gh_u4 libiconv_open(gh_byte *param_1,gh_byte *param_2);
extern gh_u4 libiconv_close(void *param_1);
extern int compare_by_index(int param_1,int param_2);
extern int compare_by_name(gh_u4 *param_1,gh_u4 *param_2);
extern char locale_charset(void);
extern gh_uint __aeabi_uidiv(gh_uint param_1,gh_uint param_2);
extern gh_uint __aeabi_idiv(gh_uint param_1,gh_uint param_2);
extern void __libc_csu_init(); /* K&R: 参数不可信/不可解析 */
extern void __libc_csu_fini(); /* K&R: 参数不可信/不可解析 */

/* ---- XUnzip(C++ XZip/TUnzip) → C 接口（mangled 符号 1:1，见 01-static/symtab）----
 * 原厂 XUnzip.cpp 为 C++ 类静态方法，Ghidra 渲染 TUnzip::X(...) 在 C 中非法。
 * 转写：TUnzip 实例指针作首参（this），其余参数与原厂签名逐项对齐。 */
extern gh_u4 _ZN6TUnzip4OpenEPvjj(TUnzip*, void*, gh_uint, gh_uint); /* TUnzip::Open(void*,uint,DWORD) */
extern gh_u4 _ZN6TUnzip3GetEiP8ZIPENTRY(TUnzip*, int, ZIPENTRY*);   /* TUnzip::Get(int,ZIPENTRY*) */
extern gh_u4 _ZN6TUnzip4FindEPKchPiP8ZIPENTRY(TUnzip*, char*, gh_uchar, int*, ZIPENTRY*); /* TUnzip::Find（ic=uchar，工厂指纹） */
extern gh_u4 _ZN6TUnzip5UnzipEiPvjj(TUnzip*, int, void*, gh_uint, gh_uint); /* TUnzip::Unzip */
extern gh_u4 _ZN6TUnzip5CloseEv(TUnzip*);                            /* TUnzip::Close */
/* C++ operator new/delete（libstdc++ 符号，NEEDED libstdc++） */
extern void * _Znwj(unsigned int size);  /* operator new(uint)：libstdc++ 供应 */
extern void   _ZdlPv(void *p);           /* operator delete(void*) */

#endif

/* ==== P3 链接期依赖：上游库 / libc 被调函数（原以隐式声明调用，现显式声明真实原型）==== */
extern int __isoc99_sscanf(char *param_1,char *param_2,...); /* glibc C99 sscanf */
extern gh_u4 libiconv(gh_u4 param_1,void *param_2,void *param_3,void *param_4,void *param_5); /* iconv 主函数；第1参为 libiconv_open 返回的句柄(32位) */
extern int compress(void *param_1,gh_u4 *param_2,void *param_3,gh_u4 param_4); /* zlib: (dest,destLen,src,srcLen) */
extern int uncompress(void *param_1,gh_u4 *param_2,void *param_3,gh_u4 param_4); /* zlib */
extern void * MP3InitDecoder(void); /* Helix: 返回解码器句柄 */
extern int shmget(gh_u4 param_1,gh_u4 param_2,gh_u4 param_3); /* SysV IPC */
extern int shmdt(void *param_1); /* SysV IPC */
extern int reboot(gh_u4 param_1); /* 不返回 */
