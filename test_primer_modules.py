#!/usr/bin/env python3
"""
测试移动后的引物设计模块是否正常工作
"""

def test_primer3_gui_import():
    """测试primer3_gui模块导入"""
    try:
        from modules.primer3_gui import MainWindow as Primer3MainWindow
        print("✅ primer3_gui模块导入成功")
        return True
    except ImportError as e:
        print(f"❌ primer3_gui模块导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ primer3_gui模块导入出现异常: {e}")
        return False

def test_primer_gui_import():
    """测试primer_gui模块导入"""
    try:
        from modules.primer_gui import MainWindow as PrimerMainWindow
        print("✅ primer_gui模块导入成功")
        return True
    except ImportError as e:
        print(f"❌ primer_gui模块导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ primer_gui模块导入出现异常: {e}")
        return False

def test_modules_init():
    """测试modules包初始化"""
    try:
        import modules
        print("✅ modules包导入成功")
        
        # 检查是否包含引物设计相关的类
        if hasattr(modules, 'Primer3MainWindow'):
            print("✅ Primer3MainWindow已在modules中可用")
        else:
            print("⚠️  Primer3MainWindow未在modules中找到")
            
        if hasattr(modules, 'PrimerMainWindow'):
            print("✅ PrimerMainWindow已在modules中可用")
        else:
            print("⚠️  PrimerMainWindow未在modules中找到")
            
        return True
    except Exception as e:
        print(f"❌ modules包导入失败: {e}")
        return False

def main():
    """运行所有测试"""
    print("开始测试移动后的引物设计模块...")
    print("=" * 50)
    
    tests = [
        test_primer3_gui_import,
        test_primer_gui_import,
        test_modules_init
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！引物设计模块移动成功。")
    else:
        print("⚠️  部分测试失败，请检查相关配置。")

if __name__ == "__main__":
    main()
