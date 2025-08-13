"""
统一翻译系统
集成分层翻译文件，提供完整的多语言支持
"""

from .core import CORE_TRANSLATIONS
from .modules import MODULE_TRANSLATIONS
from .messages import MESSAGE_TRANSLATIONS
from .help import HELP_TRANSLATIONS
from .ui_components import UI_COMPONENT_TRANSLATIONS

# 合并所有翻译字典
TRANSLATIONS = {
    'zh_CN': {
        **CORE_TRANSLATIONS['zh_CN'],
        **MODULE_TRANSLATIONS['zh_CN'],
        **MESSAGE_TRANSLATIONS['zh_CN'],
        **HELP_TRANSLATIONS['zh_CN'],
        **UI_COMPONENT_TRANSLATIONS['zh_CN'],
    },
    'en_US': {
        **CORE_TRANSLATIONS['en_US'],
        **MODULE_TRANSLATIONS['en_US'],
        **MESSAGE_TRANSLATIONS['en_US'],
        **HELP_TRANSLATIONS['en_US'],
        **UI_COMPONENT_TRANSLATIONS['en_US'],
    }
}


class Translator:
    """统一翻译器类"""
    
    def __init__(self):
        self.current_language = 'zh_CN'  # 默认中文
    
    def set_language(self, language):
        """设置当前语言"""
        if language in TRANSLATIONS:
            self.current_language = language
            return True
        return False
    
    def tr(self, text):
        """翻译文本到当前语言"""
        if self.current_language in TRANSLATIONS:
            return TRANSLATIONS[self.current_language].get(text, text)
        return text
    
    def get_current_language(self):
        """获取当前语言代码"""
        return self.current_language


# 全局翻译器实例
_translator = Translator()

def tr(text):
    """全局翻译函数"""
    return _translator.tr(text)

def set_language(language):
    """设置全局语言"""
    return _translator.set_language(language)

def get_current_language():
    """获取当前语言"""
    return _translator.get_current_language()

# 向后兼容的别名
translations = _translator