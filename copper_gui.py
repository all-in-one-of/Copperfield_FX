import sys, os
import logging

from PyQt4 import QtGui, QtCore

logging.basicConfig(level=logging.DEBUG)

os.environ['PYOPENCL_COMPILER_OUTPUT'] = "1"

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    app = QtGui.QApplication(sys.argv)
    QtGui.QFontDatabase.addApplicationFont('media/fonts')
    app.setStyle(QtGui.QStyleFactory.create('Plastique'))
    app.setWindowIcon(QtGui.QIcon('icons/copper_icon.png'))

    # Create and display the splash screen
    splash_pix = QtGui.QPixmap('media/splash_screen.png')
    splash = QtGui.QSplashScreen(splash_pix, QtCore.Qt.WindowStaysOnTopHint)
    splash.show()
    app.processEvents()

    # Create main window
    from gui.main_window import MainWindow
    
    window = MainWindow()
    window.load_style()

    # Move main window to desktop center
    desktop = QtGui.QApplication.desktop()
    screenWidth = desktop.width()
    screenHeight = desktop.height()
    x = (screenWidth - window.width()) / 2
    y = (screenHeight - window.height()) / 2
    window.move(x, y)

    # Show main window
    window.show()
    splash.finish(window)
    window.raise_()
    window.activateWindow()

    window.open_project(make_test_project=True)

    sys.exit(app.exec_())