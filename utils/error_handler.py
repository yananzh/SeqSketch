"""
统一错误处理模块
提供标准化的错误处理和消息格式
"""

import logging
from typing import Optional, Union
import translations


class StandardErrorHandler:
    """标准化错误处理器"""
    
    @staticmethod
    def format_error(error: Union[str, Exception], context: str = "", use_translation: bool = True) -> str:
        """
        格式化错误消息
        
        Args:
            error: 错误信息或异常对象
            context: 错误上下文
            use_translation: 是否使用翻译
            
        Returns:
            格式化后的错误消息
        """
        if isinstance(error, Exception):
            error_msg = str(error)
        else:
            error_msg = error
        
        if context:
            if use_translation:
                formatted_msg = translations.tr("{context}发生错误: {error}").format(
                    context=context, error=error_msg
                )
            else:
                formatted_msg = f"{context}发生错误: {error_msg}"
        else:
            if use_translation:
                formatted_msg = translations.tr("错误: {error}").format(error=error_msg)
            else:
                formatted_msg = f"错误: {error_msg}"
        
        return formatted_msg
    
    @staticmethod
    def log_error(logger: logging.Logger, error: Union[str, Exception], 
                  context: str = "", exception: Optional[Exception] = None):
        """
        记录错误日志
        
        Args:
            logger: 日志记录器
            error: 错误信息
            context: 错误上下文
            exception: 异常对象（用于记录堆栈跟踪）
        """
        formatted_msg = StandardErrorHandler.format_error(error, context, use_translation=False)
        
        if exception:
            logger.exception(formatted_msg)
        else:
            logger.error(formatted_msg)


class ErrorCode:
    """标准错误代码"""
    
    # 文件操作错误
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_READ_ERROR = "FILE_READ_ERROR" 
    FILE_WRITE_ERROR = "FILE_WRITE_ERROR"
    FILE_FORMAT_ERROR = "FILE_FORMAT_ERROR"
    
    # 数据处理错误
    INVALID_INPUT = "INVALID_INPUT"
    PROCESSING_ERROR = "PROCESSING_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    
    # 网络错误
    NETWORK_ERROR = "NETWORK_ERROR"
    API_ERROR = "API_ERROR"
    
    # 依赖错误
    DEPENDENCY_ERROR = "DEPENDENCY_ERROR"
    IMPORT_ERROR = "IMPORT_ERROR"


class BioSeqError(Exception):
    """BioSeq Analyzer 自定义异常基类"""
    
    def __init__(self, message: str, error_code: str = "", context: str = ""):
        self.message = message
        self.error_code = error_code
        self.context = context
        super().__init__(self.message)
    
    def format_message(self, use_translation: bool = True) -> str:
        """格式化错误消息"""
        return StandardErrorHandler.format_error(self.message, self.context, use_translation)


class FileProcessingError(BioSeqError):
    """文件处理错误"""
    pass


class SequenceAnalysisError(BioSeqError):
    """序列分析错误"""
    pass


class NetworkError(BioSeqError):
    """网络错误"""
    pass


class DependencyError(BioSeqError):
    """依赖错误"""
    pass
