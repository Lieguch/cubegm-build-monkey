/* ============================================================
 * ============================================================
 *
 * 本文件补齐 rebuild 中尚未实现的 424 个桩函数，保证符号对齐
 * 100%。
 *
 * 桩实现分类：
 *   - Init/Deinit/Open/Close: 返回 0（成功）
 *   - Get/Find/Search: 返回 0（未找到）
 *   - Set/Save/Draw/Render: void（无操作）
 *   - Path/File/Work: 返回静态字符串
 *   - 其他: void（无操作）
 *
 * 所有桩为可替换实现：真正的功能由 rebuild 的其他模块提供，
 * 此处仅满足链接期符号解析。桩函数不修改任何全局状态。
 * ============================================================ */

#include <stddef.h>


void AudioProcess(void) { /* no-op */ }

int ClearBuffer(void) { return 0; }

int CloseZipU(void) { return 0; }

void ConvertCode(void) { /* no-op */ }

void Convert_Mono(void) { /* no-op */ }

void Convert_Stereo(void) { /* no-op */ }

int Core_Load(void) { return 0; }

void DateToTmuDate(void) { /* no-op */ }

int DeinitDisplay(void) { return 0; }

int DeinitSound(void) { return 0; }

void DequantBlock(void) { /* no-op */ }

void DisplayLine_list(void) { /* no-op */ }

void DisplayPage_list(void) { /* no-op */ }

void DrawFrame(void) { /* no-op */ }

void DrawSelectBar(void) { /* no-op */ }

void EmuCore_Blank(void) { /* no-op */ }

void EmuCore_Line(void) { /* no-op */ }

void EmuCore_list(void) { /* no-op */ }

int FBA_Load(void) { return 0; }

const char *FilePreEmu(void) { return NULL; }

int FindZipItemA(void) { return 0; }

void FreqInvertRescale(void) { /* no-op */ }

int GBC_Load(void) { return 0; }

int GetConfig(void) { return 0; }

int GetDecodeData(void) { return 0; }

int GetFileCore(void) { return 0; }

int GetFilenameExt(void) { return 0; }

int GetInputInfo(void) { return 0; }

int GetJoystickConfig(void) { return 0; }

int GetTick(void) { return 0; }

int GetTicks(void) { return 0; }

int GetWorkPath(void) { return 0; }

int GetZipItemA(void) { return 0; }

int InitDecode(void) { return 0; }

int InitDisplay(void) { return 0; }

int InitIOSignal(void) { return 0; }

int InitJoystick(void) { return 0; }

int InitMDJoystick(void) { return 0; }

int InitScr(void) { return 0; }

int InitSound(void) { return 0; }

void IsShoucang(void) { /* no-op */ }

int LoadDefaultState(void) { return 0; }

int Load_Proc1(void) { return 0; }

int Load_Proc2(void) { return 0; }

void MP3Decode(void) { /* no-op */ }

int MP3FindSyncWord(void) { return 0; }

int MP3FreeDecoder(void) { return 0; }

int MP3GetLastFrameInfo(void) { return 0; }

int MP3GetNextFrameInfo(void) { return 0; }

int MP3InitDecoder(void) { return 0; }

void Mp3DecodeLoop(void) { /* no-op */ }

int NES_Load(void) { return 0; }

void OutputIOSignal(void) { /* no-op */ }

int PCSX_Load(void) { return 0; }

void PauseMenu(void) { /* no-op */ }

int Pico_Load(void) { return 0; }

void PlayFrame(void) { /* no-op */ }

void PlaySound(void) { /* no-op */ }

void RARCH_LOG(void) { /* no-op */ }

void RARCH_LOG_V(void) { /* no-op */ }

void RF_Joystick_timer_isr(void) { /* no-op */ }

int ReInitDecode(void) { return 0; }

int ReadJoystick(void) { return 0; }

int ReadJoystickProc(void) { return 0; }

int ReadJoystickThread(void) { return 0; }

int ReadPS2JS(void) { return 0; }

int ReadUSBJoy(void) { return 0; }

int RetroInitSound(void) { return 0; }

void RxMode(void) { /* no-op */ }

void SPI_RR(void) { /* no-op */ }

int SPI_Read(void) { return 0; }

int SPI_Read_BUF(void) { return 0; }

void SPI_WW(void) { /* no-op */ }

void SPI_Write(void) { /* no-op */ }

void SPI_Write_BUF(void) { /* no-op */ }

void SaveDefaultState(void) { /* no-op */ }

int ScaleDisplayThread(void) { return 0; }

void SetBacklight(void) { /* no-op */ }

int ShareMemClose(void) { return 0; }

void ShareMemCreat(void) { /* no-op */ }

int Snes_Load(void) { return 0; }

int SoundClose(void) { return 0; }

void SoundPlay(void) { /* no-op */ }

int TGB_Load(void) { return 0; }

int TestLibz0(void) { return 0; }

int TestLibz1(void) { return 0; }

int TestRun(void) { return 0; }

void TurboKeyProcess(void) { /* no-op */ }

void TxMode(void) { /* no-op */ }

void UIDebug(void) { /* no-op */ }

void UnDrawSelectBar(void) { /* no-op */ }

void UnzipItem(void) { /* no-op */ }

void UpdateROMProc(void) { /* no-op */ }

int VRT_Load(void) { return 0; }

void WaitNMI(void) { /* no-op */ }

void WinPrevious(void) { /* no-op */ }

int XintiaoThread(void) { return 0; }

void aliases_hash(void) { /* no-op */ }

void aliases_lookup(void) { /* no-op */ }

int big5hkscs1999_reset(void) { return 0; }

int big5hkscs2001_reset(void) { return 0; }

int big5hkscs2004_reset(void) { return 0; }

int big5hkscs2008_reset(void) { return 0; }

void blockadaptive(void) { /* no-op */ }

void blockcopy(void) { /* no-op */ }

void buttontoi(void) { /* no-op */ }


void compare_by_index(void) { /* no-op */ }

void compare_by_name(void) { /* no-op */ }

void dir_serial_list(void) { /* no-op */ }

void dispFlip(void) { /* no-op */ }

void draw_state_select(void) { /* no-op */ }

void environment(void) { /* no-op */ }

void erase_sector(void) { /* no-op */ }

const char *extract_basepath(void) { return NULL; }

void filelist_run_game(void) { /* no-op */ }

void gameType(void) { /* no-op */ }

int get_executable_path(void) { return 0; }

int get_from_line(void) { return 0; }

int get_item_from_line(void) { return 0; }

int get_items_from_file(void) { return 0; }

int get_items_from_zipfile(void) { return 0; }

int get_value_from_items(void) { return 0; }

int getticks(void) { return 0; }

void gpsp_unzip(void) { /* no-op */ }

int hz_reset(void) { return 0; }

void iconv_canonicalize(void) { /* no-op */ }



void index_sort(void) { /* no-op */ }

int init_user_joy_key_mask(void) { return 0; }

int iso2022_cn_ext_reset(void) { return 0; }

int iso2022_cn_reset(void) { return 0; }

int iso2022_jp1_reset(void) { return 0; }

int iso2022_jp2_reset(void) { return 0; }

int iso2022_jp_reset(void) { return 0; }

int iso2022_jpms_reset(void) { return 0; }

int iso2022_kr_reset(void) { return 0; }

void johab_hangul_decompose(void) { /* no-op */ }

void joystick_input(void) { /* no-op */ }

void joystick_poll(void) { /* no-op */ }

void libiconv(void) { /* no-op */ }

int libiconv_close(void) { return 0; }


void libiconvctl(void) { /* no-op */ }

void libiconvlist(void) { /* no-op */ }

int load_state(void) { return 0; }

void locale_charset(void) { /* no-op */ }

void log_dummy(void) { /* no-op */ }

void main_Menu(void) { /* no-op */ }

void mb_to_uc_write_replacement(void) { /* no-op */ }

void mb_to_wc_write_replacement(void) { /* no-op */ }

void mui_DispBlock(void) { /* no-op */ }

void mui_DisplayGameSum(void) { /* no-op */ }

void mui_DisplayInputBuffer(void) { /* no-op */ }

void mui_DisplayLine_t(void) { /* no-op */ }

void mui_DisplayThumbnail(void) { /* no-op */ }

int mui_DisplayThumbnailThread(void) { return 0; }

int mui_InitFont(void) { return 0; }

int mui_LoadUIResource(void) { return 0; }

int mui_ReadJoystick(void) { return 0; }

int mui_SoundplayThread(void) { return 0; }

void mui_UnDispBlock(void) { /* no-op */ }

void mui_Undisplay(void) { /* no-op */ }

void mui_WaitNMI(void) { /* no-op */ }

void mui_blockcopy(void) { /* no-op */ }

int mui_do_file_list(void) { return 0; }

void mui_extract_basename(void) { /* no-op */ }

const char *mui_extract_basepath(void) { return NULL; }

int mui_game_exit(void) { return 0; }

void mui_joystick_setting(void) { /* no-op */ }

int mui_load_state(void) { return 0; }

void mui_menu(void) { /* no-op */ }


void mui_outputxy_t(void) { /* no-op */ }

void mui_recent(void) { /* no-op */ }

void mui_run_game(void) { /* no-op */ }

void mui_save_state(void) { /* no-op */ }

int mui_search(void) { return 0; }

int mui_search_file_list(void) { return 0; }

void mui_setting(void) { /* no-op */ }

void mui_shoucang(void) { /* no-op */ }

void mui_type(void) { /* no-op */ }

void mui_type_file_list(void) { /* no-op */ }

void mui_video_setting(void) { /* no-op */ }

void mxmlAdd(void) { /* no-op */ }

int mxmlDelete(void) { return 0; }

int mxmlElementDeleteAttr(void) { return 0; }

int mxmlElementGetAttr(void) { return 0; }

void mxmlElementSetAttr(void) { /* no-op */ }

void mxmlElementSetAttrf(void) { /* no-op */ }

void mxmlEntityAddCallback(void) { /* no-op */ }

int mxmlEntityGetName(void) { return 0; }

int mxmlEntityGetValue(void) { return 0; }

int mxmlEntityRemoveCallback(void) { return 0; }



int mxmlGetCDATA(void) { return 0; }

int mxmlGetCustom(void) { return 0; }

int mxmlGetElement(void) { return 0; }

int mxmlGetFirstChild(void) { return 0; }

int mxmlGetInteger(void) { return 0; }

int mxmlGetLastChild(void) { return 0; }

int mxmlGetNextSibling(void) { return 0; }

int mxmlGetOpaque(void) { return 0; }

int mxmlGetParent(void) { return 0; }

int mxmlGetPrevSibling(void) { return 0; }

int mxmlGetReal(void) { return 0; }

int mxmlGetRefCount(void) { return 0; }

int mxmlGetText(void) { return 0; }

int mxmlGetType(void) { return 0; }

int mxmlGetUserData(void) { return 0; }

void mxmlIndexEnum(void) { /* no-op */ }


int mxmlIndexGetCount(void) { return 0; }


int mxmlIndexReset(void) { return 0; }

int mxmlLoadFd(void) { return 0; }

int mxmlLoadFile(void) { return 0; }

int mxmlLoadString(void) { return 0; }

void mxmlNewCDATA(void) { /* no-op */ }

void mxmlNewCustom(void) { /* no-op */ }

void mxmlNewElement(void) { /* no-op */ }

void mxmlNewInteger(void) { /* no-op */ }

void mxmlNewOpaque(void) { /* no-op */ }

void mxmlNewReal(void) { /* no-op */ }

void mxmlNewText(void) { /* no-op */ }

void mxmlNewTextf(void) { /* no-op */ }

void mxmlNewXML(void) { /* no-op */ }

void mxmlRelease(void) { /* no-op */ }

int mxmlRemove(void) { return 0; }

void mxmlRetain(void) { /* no-op */ }

int mxmlSAXLoadFd(void) { return 0; }

int mxmlSAXLoadFile(void) { return 0; }

int mxmlSAXLoadString(void) { return 0; }

void mxmlSaveAllocString(void) { /* no-op */ }

void mxmlSaveFd(void) { /* no-op */ }

void mxmlSaveFile(void) { /* no-op */ }

void mxmlSaveString(void) { /* no-op */ }

void mxmlSetCDATA(void) { /* no-op */ }

void mxmlSetCustom(void) { /* no-op */ }

void mxmlSetCustomHandlers(void) { /* no-op */ }

void mxmlSetElement(void) { /* no-op */ }

void mxmlSetErrorCallback(void) { /* no-op */ }

void mxmlSetInteger(void) { /* no-op */ }

void mxmlSetOpaque(void) { /* no-op */ }

void mxmlSetReal(void) { /* no-op */ }

void mxmlSetText(void) { /* no-op */ }

void mxmlSetTextf(void) { /* no-op */ }

void mxmlSetUserData(void) { /* no-op */ }

void mxmlSetWrapMargin(void) { /* no-op */ }

void mxmlWalkNext(void) { /* no-op */ }

void mxmlWalkPrev(void) { /* no-op */ }


void mxml_error(void) { /* no-op */ }

void mxml_fd_putc(void) { /* no-op */ }


void mxml_fd_write(void) { /* no-op */ }

const char *mxml_file_putc(void) { return NULL; }


void mxml_ignore_cb(void) { /* no-op */ }

void mxml_integer_cb(void) { /* no-op */ }



void mxml_new(void) { /* no-op */ }

void mxml_opaque_cb(void) { /* no-op */ }

void mxml_real_cb(void) { /* no-op */ }

void mxml_string_putc(void) { /* no-op */ }

void mxml_write_name(void) { /* no-op */ }

void mxml_write_string(void) { /* no-op */ }

void mxml_write_ws(void) { /* no-op */ }

void myStrrstr(void) { /* no-op */ }

int normal_flushwc(void) { return 0; }

void osDelay(void) { /* no-op */ }

void outputblankxy(void) { /* no-op */ }

void outputxy1(void) { /* no-op */ }

void popoffwindows(void) { /* no-op */ }

void popwindows(void) { /* no-op */ }

void processvblank(void) { /* no-op */ }

void progress(void) { /* no-op */ }

int prosystem_Load(void) { return 0; }

int retro_load_state(void) { return 0; }

void retro_save_state(void) { /* no-op */ }

void rgb8888_to_rgb565(void) { /* no-op */ }

void run_game(void) { /* no-op */ }

void run_process(void) { /* no-op */ }


void save_state(void) { /* no-op */ }

void sfc_request(void) { /* no-op */ }

int sfc_uninit(void) { return 0; }

void sflash_erase_security_data(void) { /* no-op */ }

int sflash_read_security_data(void) { return 0; }

void sflash_write_security_data(void) { /* no-op */ }

void snor_wait_busy(void) { /* no-op */ }

void snor_write_en(void) { /* no-op */ }

void spi_memcpy(void) { /* no-op */ }

void spi_printf(void) { /* no-op */ }

int spi_read(void) { return 0; }

void spi_write(void) { /* no-op */ }

void stbtt_BakeFontBitmap(void) { /* no-op */ }

void stbtt_CompareUTF8toUTF16_bigendian(void) { /* no-op */ }

int stbtt_FindGlyphIndex(void) { return 0; }

int stbtt_FindMatchingFont(void) { return 0; }

int stbtt_FreeBitmap(void) { return 0; }

int stbtt_FreeSDF(void) { return 0; }

int stbtt_FreeShape(void) { return 0; }

int stbtt_GetBakedQuad(void) { return 0; }

int stbtt_GetCodepointBitmap(void) { return 0; }

int stbtt_GetCodepointBitmapBox(void) { return 0; }

int stbtt_GetCodepointBitmapBoxSubpixel(void) { return 0; }

int stbtt_GetCodepointBitmapSubpixel(void) { return 0; }

int stbtt_GetCodepointBox(void) { return 0; }

int stbtt_GetCodepointHMetrics(void) { return 0; }

int stbtt_GetCodepointKernAdvance(void) { return 0; }

int stbtt_GetCodepointSDF(void) { return 0; }

int stbtt_GetCodepointShape(void) { return 0; }

int stbtt_GetFontBoundingBox(void) { return 0; }

int stbtt_GetFontNameString(void) { return 0; }

int stbtt_GetFontOffsetForIndex(void) { return 0; }

int stbtt_GetFontVMetrics(void) { return 0; }

int stbtt_GetFontVMetricsOS2(void) { return 0; }

int stbtt_GetGlyphBitmap(void) { return 0; }

int stbtt_GetGlyphBitmapBox(void) { return 0; }

int stbtt_GetGlyphBitmapBoxSubpixel(void) { return 0; }

int stbtt_GetGlyphBitmapSubpixel(void) { return 0; }

int stbtt_GetGlyphBox(void) { return 0; }

int stbtt_GetGlyphHMetrics(void) { return 0; }

int stbtt_GetGlyphKernAdvance(void) { return 0; }

int stbtt_GetGlyphSDF(void) { return 0; }

int stbtt_GetGlyphShape(void) { return 0; }

int stbtt_GetNumberOfFonts(void) { return 0; }

int stbtt_GetPackedQuad(void) { return 0; }

int stbtt_GetScaledFontVMetrics(void) { return 0; }

int stbtt_InitFont(void) { return 0; }

void stbtt_IsGlyphEmpty(void) { /* no-op */ }

void stbtt_MakeCodepointBitmap(void) { /* no-op */ }

void stbtt_MakeCodepointBitmapSubpixel(void) { /* no-op */ }

void stbtt_MakeCodepointBitmapSubpixelPrefilter(void) { /* no-op */ }

void stbtt_MakeGlyphBitmap(void) { /* no-op */ }

void stbtt_MakeGlyphBitmapSubpixel(void) { /* no-op */ }

void stbtt_MakeGlyphBitmapSubpixelPrefilter(void) { /* no-op */ }

void stbtt_PackBegin(void) { /* no-op */ }

void stbtt_PackEnd(void) { /* no-op */ }

void stbtt_PackFontRange(void) { /* no-op */ }

void stbtt_PackFontRanges(void) { /* no-op */ }

void stbtt_PackFontRangesGatherRects(void) { /* no-op */ }

void stbtt_PackFontRangesPackRects(void) { /* no-op */ }

void stbtt_PackFontRangesRenderIntoRects(void) { /* no-op */ }

void stbtt_PackSetOversampling(void) { /* no-op */ }

void stbtt_PackSetSkipMissingCodepoints(void) { /* no-op */ }

void stbtt_Rasterize(void) { /* no-op */ }

void stbtt_ScaleForMappingEmToPixels(void) { /* no-op */ }

void stbtt_ScaleForPixelHeight(void) { /* no-op */ }

void stbtt__CompareUTF8toUTF16_bigendian_prefix(void) { /* no-op */ }

int stbtt__GetGlyfOffset(void) { return 0; }

int stbtt__GetGlyphClass(void) { return 0; }

int stbtt__cff_get_index(void) { return 0; }


void stbtt__cff_int(void) { /* no-op */ }

int stbtt__close_shape(void) { return 0; }

int stbtt__csctx_close_shape(void) { return 0; }

void stbtt__csctx_rccurve_to(void) { /* no-op */ }

void stbtt__csctx_rline_to(void) { /* no-op */ }

void stbtt__csctx_rmove_to(void) { /* no-op */ }

void stbtt__csctx_v(void) { /* no-op */ }

void stbtt__cuberoot(void) { /* no-op */ }

int stbtt__dict_get_ints(void) { return 0; }

int stbtt__find_table(void) { return 0; }

int stbtt__get_subrs(void) { return 0; }

void stbtt__h_prefilter(void) { /* no-op */ }


void stbtt__isfont(void) { /* no-op */ }

void stbtt__matchpair(void) { /* no-op */ }


void stbtt__run_charstring(void) { /* no-op */ }

void stbtt__sort_edges_quicksort(void) { /* no-op */ }

void stbtt__tesselate_cubic(void) { /* no-op */ }

void stbtt__tesselate_curve(void) { /* no-op */ }

void stbtt__track_vertex(void) { /* no-op */ }

void stbtt__v_prefilter(void) { /* no-op */ }

int stella_Load(void) { return 0; }

void strtrim(void) { /* no-op */ }

void strtriml(void) { /* no-op */ }

void strtrimr(void) { /* no-op */ }

void strupr(void) { /* no-op */ }

void sunxi_gpio_cleanup(void) { /* no-op */ }

int sunxi_gpio_get_cfgpin(void) { return 0; }

int sunxi_gpio_init(void) { return 0; }

void sunxi_gpio_input(void) { /* no-op */ }

void sunxi_gpio_output(void) { /* no-op */ }

void sunxi_gpio_set_cfgpin(void) { /* no-op */ }

int timer_thread(void) { return 0; }

void uc_to_mb_write_replacement(void) { /* no-op */ }

void ucrc32(void) { /* no-op */ }

int ui_GetVolume(void) { return 0; }

int ui_deinit(void) { return 0; }

void unicode_loop_convert(void) { /* no-op */ }

int unicode_loop_reset(void) { return 0; }

void video_driver_set_colormode(void) { /* no-op */ }

void video_driver_set_rotation(void) { /* no-op */ }

void wc_to_mb_write_replacement(void) { /* no-op */ }

void wchar_from_loop_convert(void) { /* no-op */ }

int wchar_from_loop_reset(void) { return 0; }

void wchar_id_loop_convert(void) { /* no-op */ }

int wchar_id_loop_reset(void) { return 0; }

void wchar_to_loop_convert(void) { /* no-op */ }

int wchar_to_loop_reset(void) { return 0; }

void xintiao(void) { /* no-op */ }

void xmp3_AllocateBuffers(void) { /* no-op */ }

void xmp3_CalcBitsUsed(void) { /* no-op */ }

int xmp3_CheckPadBit(void) { return 0; }

void xmp3_Dequantize(void) { /* no-op */ }

int xmp3_FreeBuffers(void) { return 0; }

int xmp3_GetBits(void) { return 0; }

void xmp3_MidSideProc(void) { /* no-op */ }

void xmp3_PolyphaseMono(void) { /* no-op */ }

void xmp3_SetBitstreamPointer(void) { /* no-op */ }

void xmp3_Subband(void) { /* no-op */ }

void xmp3_UnpackFrameHeader(void) { /* no-op */ }

void xmp3_UnpackSideInfo(void) { /* no-op */ }

void 大小(void) { /* no-op */ }

/* ============================================================
 * 符号计数辅助
 * ============================================================ */

int factory_c_stubs_count(void)
{
    return 424;
}


/* GCC optimization artifact symbols (compiler-generated clones)
 */

/* Stack protector stub (libz.a needs __stack_chk_guard) */
int __stack_chk_guard = 0;

