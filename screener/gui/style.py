QSS = """
* { font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial; font-size: 9.5pt; color: #24313d; }
QMainWindow, QWidget#Central { background: #f4f6f9; }
QToolBar { background: #17324d; border: none; padding: 4px 6px; spacing: 6px; }
QToolBar QToolButton { color: #ffffff; background: transparent; border: 1px solid transparent;
    border-radius: 4px; padding: 5px 10px; font-weight: 600; }
QToolBar QToolButton:hover { background: #24496d; border-color: #35618c; }
QToolBar QToolButton:disabled { color: #7f93a8; }
QToolBar QLabel { color: #d7e2ec; }
QToolBar QProgressBar { background: #24496d; border: none; border-radius: 3px; color: #fff; max-height: 14px;
    text-align: center; font-size: 8pt; }
QToolBar QProgressBar::chunk { background: #3fae6b; border-radius: 3px; }
QTabWidget::pane { border: 1px solid #d5dce4; background: #ffffff; top: -1px; }
QTabBar::tab { background: #e6ebf0; border: 1px solid #d5dce4; padding: 7px 16px; margin-right: 2px;
    border-top-left-radius: 5px; border-top-right-radius: 5px; color: #4a5866; }
QTabBar::tab:selected { background: #ffffff; color: #17324d; font-weight: 700; border-bottom-color: #ffffff; }
QLabel#SectionHeader { background: #17324d; color: #ffffff; font-weight: 700; padding: 4px; }
QLabel#FilterLabel { color: #33414e; }
QLabel#SubHeader { font-weight: 700; color: #17324d; padding: 4px 2px; }
QLabel#CountLabel { color: #5a6773; padding-right: 8px; }
QLabel#DetailHeader { padding: 4px 10px; }
QLabel#Banner { background: #fff8e6; border: 1px solid #f0d58c; border-radius: 4px; padding: 8px; color: #6b5200; }
QLabel#Intro { color: #4a5866; padding: 2px 2px 6px 2px; }
QLabel#SummaryBox { background: #f7f9fb; border: 1px solid #dde3ea; border-radius: 6px; padding: 10px; }
QFrame#FilterBody { background: #ffffff; border: 1px solid #d5dce4; }
QFrame#SavedBar { background: #dceaf7; border: 1px solid #c5d8ea; border-top: none; }
QPushButton { background: #ffffff; border: 1px solid #b9c4cf; border-radius: 4px; padding: 4px 12px; }
QPushButton:hover { border-color: #17324d; background: #f2f6fa; }
QPushButton#Primary { background: #1f6fb2; color: #ffffff; border-color: #1f6fb2; font-weight: 700; padding: 6px 14px; }
QPushButton#Primary:hover { background: #185a91; }
QPushButton#Primary:disabled { background: #8fb3d3; border-color: #8fb3d3; }
QPushButton#FilterToggle { border: none; font-weight: 700; color: #17324d; padding: 4px 6px; }
QComboBox, QLineEdit { background: #ffffff; border: 1px solid #b9c4cf;
    border-radius: 3px; padding: 2px 6px; min-height: 20px; }
QComboBox[active="true"] { border: 2px solid #f07f24; background: #fffaf5; }
QComboBox:focus, QLineEdit:focus { border-color: #1f6fb2; }
QTableView { background: #ffffff; alternate-background-color: #f6f9fc; gridline-color: #e6ebf0;
    selection-background-color: #cfe3f7; selection-color: #17324d; border: 1px solid #d5dce4; }
QHeaderView::section { background: #17324d; color: #ffffff; font-weight: 600; padding: 5px 6px;
    border: none; border-right: 1px solid #2c4d6e; }
QHeaderView::section:hover { background: #24496d; }
QGroupBox { font-weight: 700; color: #17324d; border: 1px solid #d5dce4; border-radius: 6px; margin-top: 10px;
    padding-top: 8px; background: #ffffff; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QStatusBar { background: #e6ebf0; color: #4a5866; }
QSplitter::handle { background: #e6ebf0; }
QListWidget { border: 1px solid #d5dce4; background: #ffffff; }
"""
