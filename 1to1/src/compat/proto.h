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
extern void spi_printf(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 ShareMemCreat(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 ShareMemClose(); /* K&R: 参数不可信/不可解析 */
extern void xintiao(); /* K&R: 参数不可信/不可解析 */
extern void XintiaoThread(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 UpdateROMProc(int param_1,int param_2);
extern void DateToTmuDate(gh_uint param_1);
extern void UpdateROM(char *param_1);
extern void TestUSBJoy(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 GetTick(); /* K&R: 参数不可信/不可解析 */
extern void WaitNMI(); /* K&R: 参数不可信/不可解析 */
extern void TestRun(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 TestLibz0(); /* K&R: 参数不可信/不可解析 */
extern void TestLibz1(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 sunxi_gpio_init(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 sunxi_gpio_set_cfgpin(int param_1,int param_2);
extern gh_uint sunxi_gpio_get_cfgpin(gh_uint param_1);
extern gh_u4 sunxi_gpio_output(); /* K&R: 参数不可信/不可解析 */
extern gh_uint sunxi_gpio_input(gh_uint param_1);
extern void sunxi_gpio_cleanup(); /* K&R: 参数不可信/不可解析 */
extern char get_from_line(char *param_1,int param_2);
extern gh_u4 GetInputInfo(char *param_1,gh_u4 param_2);
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
extern void SPI_Read_BUF(gh_u4 param_1,int param_2,int param_3);
extern void SPI_Write_BUF(gh_u4 param_1,int param_2,int param_3);
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
extern gh_u4 run_process_constprop_0(gh_u4 param_1);
extern gh_u4 InitDisplay(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 dispFlip(gh_u4 param_1,gh_u4 param_2,gh_u4 param_3,gh_u4 param_4);
extern void video_driver_set_rotation(gh_u4 param_1);
extern void video_driver_set_colormode(); /* K&R: 参数不可信/不可解析 */
extern void DeinitDisplay(); /* K&R: 参数不可信/不可解析 */
extern void InitSound(); /* K&R: 参数不可信/不可解析 */
extern void DeinitSound(); /* K&R: 参数不可信/不可解析 */
extern void PlaySound(); /* K&R: 参数不可信/不可解析 */
extern gh_uint ucrc32(gh_uint param_1,gh_byte *param_2,gh_uint param_3);
extern gh_u4 OpenZipU(void *param_1,gh_uint param_2,gh_uint param_3);
extern gh_u4 GetZipItemA(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 FindZipItemA(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 UnzipItem(int *param_1,int param_2,void *param_3,gh_uint param_4,gh_uint param_5);
extern gh_u4 CloseZipU(int *param_1);
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
extern gh_byte strupr(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 FilePreEmu(); /* K&R: 参数不可信/不可解析 */
extern gh_u1 GetWorkPath(); /* K&R: 参数不可信/不可解析 */
extern void mui_LoadSetting(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 mui_LoadUIResource(gh_u4 *param_1,gh_u4 param_2);
extern void shoucang(char *param_1);
extern gh_u4 IsShoucang(char *param_1);
extern int mui_do_file_list(int param_1,gh_byte *param_2);
extern int mui_type_file_list(int param_1,gh_byte *param_2);
extern int mui_search_file_list(int param_1,int param_2);
extern int GetTicks(); /* K&R: 参数不可信/不可解析 */
extern void mui_DisplayThumbnailThread(); /* K&R: 参数不可信/不可解析 */
extern void mui_WaitNMI(); /* K&R: 参数不可信/不可解析 */
extern void stbtt_GetFontVMetrics(); /* K&R: 参数不可信/不可解析 */
extern float stbtt_ScaleForPixelHeight(float param_1,int param_2);
extern int mui_outputxy_length_isra_19(int param_1,int param_2,gh_byte *param_3);
extern int mui_outputxy_t(int param_1,int param_2,int param_3,int param_4,gh_uint param_5,gh_byte *param_6);
extern void mui_DisplayGameSum(); /* K&R: 参数不可信/不可解析 */
extern void mui_DisplayLine_t(int param_1,int param_2,int param_3);
extern void mui_DisplayInputBuffer(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 stbtt_InitFont(int param_1,int param_2,gh_u4 param_3);
extern void mui_InitFont(); /* K&R: 参数不可信/不可解析 */
extern char strtrimr(); /* K&R: 参数不可信/不可解析 */
extern gh_byte strtriml(); /* K&R: 参数不可信/不可解析 */
extern void strtrim(); /* K&R: 参数不可信/不可解析 */
extern char get_item_from_line(gh_u4 param_1,char *param_2);
extern int get_items_from_file(char *param_1,int param_2);
extern int get_items_from_zipfile(gh_u4 param_1,int param_2);
extern char get_value_from_items(char *param_1,char *param_2,char *param_3,int param_4);
extern void mui_LoadConfig(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 gameType(); /* K&R: 参数不可信/不可解析 */
extern void LoadMenuLog(); /* K&R: 参数不可信/不可解析 */
extern void SaveMenuLog(); /* K&R: 参数不可信/不可解析 */
extern gh_uint mui_ReadJoystick(); /* K&R: 参数不可信/不可解析 */
extern int dir_serial_list(); /* K&R: 参数不可信/不可解析 */
extern void outputblankxy(); /* K&R: 参数不可信/不可解析 */
extern void DisplayLine_list(gh_u4 param_1,int param_2,int param_3);
extern void DisplayPage_list(int param_1,gh_u4 param_2,int param_3);
extern char myStrrstr(char *param_1,char *param_2);
extern void EmuCore_Blank(); /* K&R: 参数不可信/不可解析 */
extern void EmuCore_Line(int param_1,int param_2,int param_3);
extern void EmuCore_list(int param_1,gh_u4 param_2,int param_3);
extern int SeletEmuCore(gh_u4 param_1);
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
extern gh_u4 GetJoystickConfig(int param_1,gh_u4 param_2,gh_u4 param_3,gh_u4 param_4);
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
extern gh_u4 gpsp_unzip(gh_u4 param_1,gh_u4 param_2);
extern void log_dummy(gh_uint param_1,gh_u4 param_2);
extern gh_bool joystick_input(gh_uint param_1,gh_u4 param_2,gh_u4 param_3,int param_4);
extern gh_u4 environment(int param_1,gh_uint *param_2);
extern void UIDebug(int param_1,int param_2,gh_u4 param_3,gh_uint param_4);
extern void DrawFrame(gh_u2 *param_1,int param_2,int param_3,int param_4);
extern void rgb8888_to_rgb565(gh_ushort *param_1,int param_2,int param_3);
extern int GetCoreIndex(char *param_1);
extern char GetFilenameExt(); /* K&R: 参数不可信/不可解析 */
extern void extract_basepath(char *param_1,char *param_2,int param_3);
extern void init_user_joy_key_mask(int param_1,gh_u4 param_2);
extern void TurboKeyProcess(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 run_process(gh_u4 param_1,int param_2);
extern void RetroInitSound(); /* K&R: 参数不可信/不可解析 */
extern gh_bool Load_Proc1(char *param_1);
extern void Load_Proc2(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 Snes_Load(char *param_1,int param_2);
extern gh_u4 TGB_Load(char *param_1,int param_2);
extern gh_u4 prosystem_Load(char *param_1,int param_2);
extern gh_u4 stella_Load(char *param_1,int param_2);
extern gh_u4 PCSX_Load(char *param_1);
extern gh_u4 FBA_Load(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 Core_Load(char *param_1,gh_u4 param_2);
extern gh_u4 Gpsp_Load(char *param_1,int param_2);
extern gh_u4 run_game(); /* K&R: 参数不可信/不可解析 */
extern void autorun(gh_u4 param_1,char *param_2);
extern gh_u4 NES_Load(char *param_1,int param_2);
extern gh_u4 GBC_Load(char *param_1,int param_2);
extern gh_u4 VRT_Load(char *param_1,int param_2);
extern gh_u4 Pico_Load(char *param_1,int param_2);
extern gh_u4 retro_save_state(char *param_1);
extern gh_u4 retro_load_state(char *param_1);
extern void MP3FreeDecoder(); /* K&R: 参数不可信/不可解析 */
extern int MP3FindSyncWord(gh_byte *param_1,int param_2);
extern void MP3GetLastFrameInfo(int param_1,gh_u4 *param_2);
extern gh_u4 MP3GetNextFrameInfo(int param_1,gh_u4 param_2,gh_u4 param_3);
extern gh_u4 MP3Decode(int param_1,int *param_2,int *param_3,int param_4,int param_5);
extern void Convert_Stereo(gh_u2 *param_1);
extern void Convert_Mono(gh_u2 *param_1);
extern gh_u4 xmp3_UnpackFrameHeader(int *param_1,char *param_2);
extern void ClearBuffer(gh_u1 *param_1,int param_2);
extern gh_u4 mxmlElementGetAttr(int *param_1,char *param_2);
extern void mxmlElementSetAttr(int *param_1,int param_2,int param_3);
extern gh_u4 mxmlLoadFile(); /* K&R: 参数不可信/不可解析 */
extern int mxmlSaveFile(); /* K&R: 参数不可信/不可解析 */
extern void mxmlDelete(); /* K&R: 参数不可信/不可解析 */
extern int mxmlFindElement(int param_1,int param_2,char *param_3,int param_4,char *param_5,int param_6);
extern gh_uint sfc_request(gh_uint *param_1,gh_uint param_2,gh_uint *param_3,gh_uint param_4);
extern int snor_wait_busy(int param_1);
extern void snor_write_en(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 spi_write(); /* K&R: 参数不可信/不可解析 */
extern gh_u4 erase_sector(gh_u4 param_1);
extern gh_u4 spi_read(); /* K&R: 参数不可信/不可解析 */
extern void sflash_write_security_data(gh_u4 param_1,gh_u4 param_2);
extern void sflash_erase_security_data(gh_u4 param_1);
extern void sflash_read_security_data(gh_u4 param_1,gh_u4 param_2);
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

#endif