# -*- coding: utf-8 -*-
#@+leo-ver=5-thin
#@+node:ekr.20140907131341.18707: * @file ../plugins/qt_tree.py
#@@first
'''Leo's Qt tree class.'''
#@+<< imports >>
#@+node:ekr.20140907131341.18709: ** << imports >> (qt_tree.py)
import leo.core.leoGlobals as g
import leo.core.leoFrame as leoFrame
import leo.core.leoNodes as leoNodes
import leo.core.leoPlugins as leoPlugins # Uses leoPlugins.TryNext.
import leo.plugins.qt_text as qt_text
from leo.core.leoQt import QtConst, QtCore, QtGui, QtWidgets
import re
#@-<< imports >>
#@+others
#@+node:ekr.20160514120051.1: ** class LeoQtTree
class LeoQtTree(leoFrame.LeoTree):
    '''Leo Qt tree class'''
    callbacksInjected = False # A class var.
    #@+others
    #@+node:ekr.20110605121601.18404: *3* qtree.Birth
    #@+node:ekr.20110605121601.18405: *4* qtree.__init__
    def __init__(self, c, frame):
        '''Ctor for the LeoQtTree class.'''
        leoFrame.LeoTree.__init__(self, frame)
            # Init the base class.
        self.c = c
        # Widget independent status ivars...
        self.contracting = False
        self.expanding = False
        self.prev_v = None
        self.redrawing = False
        self.redrawCount = 0 # Count for debugging.
        self.revertHeadline = None # Previous headline text for abortEditLabel.
        self.selecting = False
        # Debugging...
        self.nodeDrawCount = 0
        self.traceCallersFlag = False # Enable traceCallers method.
        # Associating items with position and vnodes...
        self.item2positionDict = {}
        self.item2vnodeDict = {}
        self.position2itemDict = {}
        self.vnode2itemsDict = {} # values are lists of items.
        self.editWidgetsDict = {} # keys are native edit widgets, values are wrappers.
        self.reloadSettings()
        # Components.
        self.canvas = self # An official ivar used by Leo's core.
        self.headlineWrapper = qt_text.QHeadlineWrapper # This is a class.
        self.treeWidget = w = frame.top.leo_ui.treeWidget # An internal ivar.
            # w is a LeoQTreeWidget, a subclass of QTreeWidget.
        # "declutter", node appearance tweaking
        self.declutter_patterns = None  # list of pairs of patterns for decluttering
        self.declutter_update = False  # true when update on idle needed
        g.registerHandler('save1', self.clear_visual_icons)
        g.registerHandler('headkey2', self.update_appearance)
        g.registerHandler('idle', self.update_appearance_idle)

        if 0: # Drag and drop
            w.setDragEnabled(True)
            w.viewport().setAcceptDrops(True)
            w.showDropIndicator = True
            w.setAcceptDrops(True)
            w.setDragDropMode(w.InternalMove)
            if 1: # Does not work

                def dropMimeData(self, data, action, row, col, parent):
                    g.trace()
                # w.dropMimeData = dropMimeData

                def mimeData(self, indexes):
                    g.trace()
        # Early inits...
        try:
            w.headerItem().setHidden(True)
        except Exception:
            pass
        n = c.config.getInt('icon-height')
        w.setIconSize(QtCore.QSize(160, n))
    #@+node:ekr.20110605121601.17866: *4* qtree.get_name
    def getName(self):
        '''Return the name of this widget: must start with "canvas".'''
        return 'canvas(tree)'
    #@+node:ekr.20110605121601.18406: *4* qtree.initAfterLoad
    def initAfterLoad(self):
        '''Do late-state inits.'''
        # Called by Leo's core.
        c = self.c
        # w = c.frame.top
        tw = self.treeWidget
        if not LeoQtTree.callbacksInjected:
            LeoQtTree.callbacksInjected = True
            self.injectCallbacks() # A base class method.
        tw.itemDoubleClicked.connect(self.onItemDoubleClicked)
        tw.itemClicked.connect(self.onItemClicked)
        tw.itemSelectionChanged.connect(self.onTreeSelect)
        tw.itemCollapsed.connect(self.onItemCollapsed)
        tw.itemExpanded.connect(self.onItemExpanded)
        tw.customContextMenuRequested.connect(self.onContextMenu)
        # tw.onItemChanged.connect(self.onItemChanged)
        g.app.gui.setFilter(c, tw, self, tag='tree')
        # 2010/01/24: Do not set this here.
        # The read logic sets c.changed to indicate nodes have changed.
        # c.setChanged(False)
    #@+node:ekr.20110605121601.17871: *4* qtree.reloadSettings
    def reloadSettings(self):
        '''LeoQtTree.'''
        c = self.c
        self.auto_edit = c.config.getBool('single_click_auto_edits_headline', False)
        self.enable_drag_messages = c.config.getBool("enable_drag_messages")
        self.select_all_text_when_editing_headlines = c.config.getBool(
            'select_all_text_when_editing_headlines')
        self.stayInTree = c.config.getBool('stayInTreeAfterSelect')
        self.use_chapters = c.config.getBool('use_chapters')
        self.use_declutter = c.config.getBool('tree-declutter', default=False)

    #@+node:ekr.20110605121601.17940: *4* qtree.wrapQLineEdit
    def wrapQLineEdit(self, w):
        '''A wretched kludge for MacOs k.masterMenuHandler.'''
        c = self.c
        if isinstance(w, QtWidgets.QLineEdit):
            wrapper = self.edit_widget(c.p)
        else:
            wrapper = w
        return wrapper
    #@+node:ekr.20110605121601.17868: *3* qtree.Debugging & tracing
    def error(self, s):
        if not g.app.unitTesting:
            g.trace('LeoQtTree Error: %s' % (s), g.callers())

    def traceItem(self, item):
        if item:
            # A QTreeWidgetItem.
            return 'item %s: %s' % (id(item), self.getItemText(item))
        else:
            return '<no item>'

    def traceCallers(self):
        if self.traceCallersFlag:
            return g.callers(5, excludeCaller=True)
        else:
            return ''
    #@+node:ekr.20110605121601.17872: *3* qtree.Drawing
    #@+node:ekr.20110605121601.18408: *4* qtree.clear
    def clear(self):
        '''Clear all widgets in the tree.'''
        w = self.treeWidget
        w.clear()
    #@+node:ekr.20110605121601.17873: *4* qtree.full_redraw & helpers
    def full_redraw(self, p=None, scroll=True, forceDraw=False):
        '''
        Redraw all visible nodes of the tree.
        Preserve the vertical scrolling unless scroll is True.
        '''
        trace = False and not g.app.unitTesting
        verbose = False
        c = self.c
        if g.app.disable_redraw:
            if trace: g.trace('*** disabled', g.callers())
            return
        if self.busy():
            return g.trace('*** full_redraw: busy!', g.callers())
        # Cancel the delayed redraw request.
        c.requestLaterRedraw = False
        if not p:
            p = c.currentPosition()
        elif c.hoistStack and p.h.startswith('@chapter') and p.hasChildren():
            # Make sure the current position is visible.
            # Part of fix of bug 875323: Hoist an @chapter node leaves a non-visible node selected.
            p = p.firstChild()
            if trace: g.trace('selecting', p.h)
            c.frame.tree.select(p)
            c.setCurrentPosition(p)
        else:
            c.setCurrentPosition(p)
        self.redrawCount += 1
        if trace: t1 = g.getTime()
        self.initData()
        self.nodeDrawCount = 0
        try:
            self.redrawing = True
            self.drawTopTree(p)
        finally:
            self.redrawing = False
        self.setItemForCurrentPosition(scroll=scroll)
        if trace:
            if verbose:
                theTime = g.timeSince(t1)
                g.trace('** %s: scroll %5s drew %3s nodes in %s' % (
                    self.redrawCount, scroll, self.nodeDrawCount, theTime), g.callers())
            else:
                g.trace('**', self.redrawCount, g.callers())
        return p # Return the position, which may have changed.

    # Compatibility
    redraw = full_redraw
    redraw_now = full_redraw
    #@+node:tbrown.20150807093655.1: *5* qtree.clear_visual_icons
    def clear_visual_icons(self, tag, keywords):
        """clear_visual_icons - remove 'declutter' icons before save

        this method must return None to tell Leo to continue normal processing

        :param str tag: 'save1'
        :param dict keywords: Leo hook keywords
        """

        if not self.use_declutter:
            return None

        c = keywords['c']
        if c != self.c:
            return None

        if c.config.getBool('tree-declutter', default=False):
            com = c.editCommands
            for nd in c.all_unique_positions():
                icons = [i for i in com.getIconList(nd) if 'visualIcon' not in i]
                com.setIconList(nd, icons, False)

        self.declutter_update = True

        return None
    #@+node:tbrown.20150807090639.1: *5* qtree.declutter_node & helpers
    def declutter_node(self, c, p, item):
        """declutter_node - change the appearance of a node

        :param commander c: commander containing node
        :param position p: position of node
        :param QWidgetItem item: tree node widget item
        """
        trace = False and not g.unitTesting
        if self.declutter_patterns is None:
            self.declutter_patterns = []
            warned = False
            lines = c.config.getData("tree-declutter-patterns")
            for line in lines:
                try:
                    cmd, arg = line.split(None, 1)
                except ValueError:
                    # Allow empty arg, and guard against user errors.
                    cmd = line.strip()
                    arg = ''
                if cmd.startswith('#'):
                    pass
                elif cmd == 'RULE':
                    self.declutter_patterns.append((re.compile(arg), []))
                else:
                    if self.declutter_patterns:
                        self.declutter_patterns[-1][1].append((cmd, arg))
                    elif not warned:
                        warned = True
                        g.log('Declutter patterns must start with RULE*',
                            color='error')
            if trace: g.trace('PATTERNS', self.declutter_patterns)
        text = str(item.text(0)) if g.isPython3 else g.u(item.text(0))
        new_icons = []
        for pattern, cmds in self.declutter_patterns:
            for func in (pattern.match, pattern.search):
                m = func(text)
                if m:
                    # if trace: g.trace(func.__name__, text)
                    for cmd, arg in cmds:
                        if self.declutter_replace(arg, cmd, item, m, pattern, text):
                            pass
                        else:
                            self.declutter_style(arg, c, cmd, item, new_icons)
                    break # Don't try pattern.search if pattern.match succeeds.
        com = c.editCommands
        allIcons = com.getIconList(p)
        icons = [i for i in allIcons if 'visualIcon' not in i]
        if len(allIcons) != len(icons) or new_icons:
            for icon in new_icons:
                com.appendImageDictToList(
                    icons, icon, 2, on='vnode', visualIcon='1'
                )
            com.setIconList(p, icons, False)
    #@+node:ekr.20171122064635.1: *6* qtree.declutter_replace
    def declutter_replace(self, arg, cmd, item, m, pattern, text):
        '''
        Execute cmd and return True if cmd is any replace command.
        '''
        if cmd == 'REPLACE':
            text = pattern.sub(arg, text)
            item.setText(0, text)
            return True
        elif cmd == 'REPLACE-HEAD':
            s = text[:m.start()]
            item.setText(0, s.rstrip())
            return True
        elif cmd == 'REPLACE-TAIL':
            s = text[m.end():]
            item.setText(0, s.lstrip())
            return True
        elif cmd == 'REPLACE-REST':
            s = text[:m.start] + text[m.end():]
            item.setText(0, s.strip())
            return True
        else:
            return False
        
    #@+node:ekr.20171122055719.1: *6* qtree.declutter_style
    def declutter_style(self, arg, c, cmd, item, new_icons):
        '''Handle style options.'''
        arg = c.styleSheetManager.expand_css_constants(arg).split()[0]
        if cmd == 'ICON':
            new_icons.append(arg)
        elif cmd == 'BG':
            item.setBackground(0, QtGui.QBrush(QtGui.QColor(arg)))
        elif cmd == 'FG':
            item.setForeground(0, QtGui.QBrush(QtGui.QColor(arg)))
        elif cmd == 'FONT':
            item.setFont(0, QtGui.QFont(arg))
        elif cmd == 'ITALIC':
            font = item.font(0)
            font.setItalic(bool(int(arg)))
            item.setFont(0, font)
        elif cmd == 'WEIGHT':
            arg = getattr(QtGui.QFont, arg, 75)
            font = item.font(0)
            font.setWeight(arg)
            item.setFont(0, font)
        elif cmd == 'PX':
            font = item.font(0)
            font.setPixelSize(int(arg))
            item.setFont(0, font)
        elif cmd == 'PT':
            font = item.font(0)
            font.setPointSize(int(arg))
            item.setFont(0, font)
    #@+node:ekr.20110605121601.17874: *5* qtree.drawChildren
    def drawChildren(self, p, parent_item):
        '''Draw the children of p if they should be expanded.'''
        trace = False and not g.unitTesting
        # if trace: g.trace('children: %5s expanded: %5s %s childIndex: %s' % (
            # p.hasChildren(),p.isExpanded(),p.h,p._childIndex))
        if not p:
            return g.trace('can not happen: no p')
        if p.hasChildren():
            if p.isExpanded():
                if trace: g.trace('expanded', p, p._childIndex)
                self.expandItem(parent_item)
                child = p.firstChild()
                while child:
                    self.drawTree(child, parent_item)
                    child.moveToNext()
            else:
                # Draw the hidden children.
                child = p.firstChild()
                while child:
                    self.drawNode(child, parent_item)
                    child.moveToNext()
                self.contractItem(parent_item)
        else:
            self.contractItem(parent_item)
    #@+node:ekr.20110605121601.17875: *5* qtree.drawNode
    def drawNode(self, p, parent_item):
        '''Draw the node p.'''
        trace = False
        c = self.c
        self.nodeDrawCount += 1
        # Allocate the item.
        item = self.createTreeItem(p, parent_item)
        # Do this now, so self.isValidItem will be true in setItemIcon.
        self.rememberItem(p, item)
        # Set the headline and maybe the icon.
        self.setItemText(item, p.h)

        if self.use_declutter:
            self.declutter_node(c, p, item)

        if p:
            self.drawItemIcon(p, item)
        if trace: g.trace(self.traceItem(item))

        return item
    #@+node:ekr.20110605121601.17876: *5* qtree.drawTopTree
    def drawTopTree(self, p):
        '''Draw the tree rooted at p.'''
        trace = False and not g.unitTesting
        c = self.c
        hPos, vPos = self.getScroll()
        self.clear()
        # Draw all top-level nodes and their visible descendants.
        if c.hoistStack:
            bunch = c.hoistStack[-1]
            p = bunch.p; h = p.h
            if len(c.hoistStack) == 1 and h.startswith('@chapter') and p.hasChildren():
                p = p.firstChild()
                while p:
                    self.drawTree(p)
                    p.moveToNext()
            else:
                self.drawTree(p)
        else:
            p = c.rootPosition()
            if trace: g.trace(p)
            while p:
                self.drawTree(p)
                p.moveToNext()
        # This method always retains previous scroll position.
        self.setHScroll(hPos)
        self.setVScroll(vPos)
        self.repaint()
    #@+node:ekr.20110605121601.17877: *5* qtree.drawTree
    def drawTree(self, p, parent_item=None):
        if g.app.gui.isNullGui:
            return
        # Draw the (visible) parent node.
        item = self.drawNode(p, parent_item)
        # Draw all the visible children.
        self.drawChildren(p, parent_item=item)
    #@+node:ekr.20110605121601.17878: *5* qtree.initData
    def initData(self):
        # g.trace('*****')
        self.item2positionDict = {}
        self.item2vnodeDict = {}
        self.position2itemDict = {}
        self.vnode2itemsDict = {}
        self.editWidgetsDict = {}
    #@+node:ekr.20110605121601.17879: *5* qtree.rememberItem
    def rememberItem(self, p, item):
        trace = False and not g.unitTesting
        if trace: g.trace('id', id(item), p)
        v = p.v
        # Update position dicts.
        itemHash = self.itemHash(item)
        self.position2itemDict[p.key()] = item
        self.item2positionDict[itemHash] = p.copy() # was item
        # Update item2vnodeDict.
        self.item2vnodeDict[itemHash] = v # was item
        # Update vnode2itemsDict.
        d = self.vnode2itemsDict
        aList = d.get(v, [])
        if item in aList:
            g.trace('*** ERROR *** item already in list: %s, %s' % (item, aList))
        else:
            aList.append(item)
        d[v] = aList
    #@+node:tbrown.20150808075906.1: *5* qtree.update_appearance
    def update_appearance(self, tag, keywords):
        """clear_visual_icons - update appearance, but can't call
        self.full_redraw() now, so just set a flag to do it on idle.

        :param str tag: 'headkey2'
        :param dict keywords: Leo hook keywords
        """
        if not self.use_declutter:
            return None
        c = keywords['c']
        if c != self.c:
            return None
        self.declutter_update = True
        return None
    #@+node:tbrown.20150808082111.1: *5* qtree.update_appearance_idle
    def update_appearance_idle(self, tag, keywords):
        """clear_visual_icons - update appearance now we're safely out of
        the redraw loop.

        :param str tag: 'idle'
        :param dict keywords: Leo hook keywords
        """
        if not self.use_declutter:
            return None
        c = keywords['c']
        if c != self.c:
            return None

        if isinstance(QtWidgets.QApplication.focusWidget(), QtWidgets.QLineEdit):
            # when search results are found in headlines headkey2 fires
            # (on the second search hit in a headline), and full_redraw()
            # below takes the headline out of edit mode, and Leo crashes,
            # probably because the find code didn't expect to leave edit
            # mode.  So don't update when a QLineEdit has focus
            return None

        if self.declutter_update:
            self.declutter_update = False
            self.full_redraw(scroll=False)
        return None
    #@+node:ekr.20110605121601.17880: *4* qtree.redraw_after_contract
    def redraw_after_contract(self, p=None):
        trace = False and not g.unitTesting
        if self.redrawing:
            return
        item = self.position2item(p)
        if item:
            if trace: g.trace('contracting item', item, p and p.h or '<no p>')
            self.contractItem(item)
        else:
            # This is not an error.
            # We may have contracted a node that was not, in fact, visible.
            if trace: g.trace('***full redraw', p and p.h or '<no p>')
            self.full_redraw(scroll=False)
    #@+node:ekr.20110605121601.17881: *4* qtree.redraw_after_expand
    def redraw_after_expand(self, p=None):
        # Important, setting scrolling to False makes the problem *worse*
        self.full_redraw(p, scroll=True)
    #@+node:ekr.20110605121601.17882: *4* qtree.redraw_after_head_changed
    def redraw_after_head_changed(self):
        trace = False and not g.unitTesting
        if self.busy(): return
        p = self.c.p
        # ew = self.edit_widget(p)
        if trace: g.trace(p.h)
        # currentItem = self.getCurrentItem()
        if p:
            h = p.h # 2010/02/09: Fix bug 518823.
            for item in self.vnode2items(p.v):
                if self.isValidItem(item):
                    self.setItemText(item, h)
        # Bug fix: 2009/10/06
        self.redraw_after_icons_changed()
    #@+node:ekr.20110605121601.17883: *4* qtree.redraw_after_icons_changed
    def redraw_after_icons_changed(self):
        trace = False and not g.unitTesting
        if self.busy(): return
        self.redrawCount += 1 # To keep a unit test happy.
        c = self.c
        if trace: g.trace(c.p.h, g.callers(4))
        # Suppress call to setHeadString in onItemChanged!
        self.redrawing = True
        try:
            self.getCurrentItem()
            for p in c.rootPosition().self_and_siblings():
                # Updates icons in p and all visible descendants of p.
                self.updateVisibleIcons(p)
        finally:
            self.redrawing = False
    #@+node:ekr.20110605121601.17884: *4* qtree.redraw_after_select
    # Important: this can not replace before/afterSelectHint.

    def redraw_after_select(self, p=None):
        '''Redraw the entire tree when an invisible node
        is selected.'''
        trace = False and not g.unitTesting
        if trace: g.trace('(LeoQtTree) busy? %s %s' % (
            self.busy(), p and p.h or '<no p>'), g.callers(4))
        # Prevent the selecting lockout from disabling the redraw.
        oldSelecting = self.selecting
        self.selecting = False
        try:
            if not self.busy():
                self.full_redraw(p, scroll=False)
        finally:
            self.selecting = oldSelecting
        # c.redraw_after_select calls tree.select indirectly.
        # Do not call it again here.
    #@+node:ekr.20140907201613.18986: *4* qtree.repaint
    def repaint(self):
        '''Repaint the widget.'''
        w = self.treeWidget
        w.repaint()
        w.resizeColumnToContents(0) # 2009/12/22
    #@+node:ekr.20110605121601.17885: *3* qtree.Event handlers
    #@+node:ekr.20110605121601.17887: *4*  qtree.Click Box
    #@+node:ekr.20110605121601.17888: *5* qtree.onClickBoxClick
    def onClickBoxClick(self, event, p=None):
        if self.busy(): return
        c = self.c
        g.doHook("boxclick1", c=c, p=p, event=event)
        g.doHook("boxclick2", c=c, p=p, event=event)
        c.outerUpdate()
    #@+node:ekr.20110605121601.17889: *5* qtree.onClickBoxRightClick
    def onClickBoxRightClick(self, event, p=None):
        if self.busy(): return
        c = self.c
        g.doHook("boxrclick1", c=c, p=p, event=event)
        g.doHook("boxrclick2", c=c, p=p, event=event)
        c.outerUpdate()
    #@+node:ekr.20110605121601.17890: *5* qtree.onPlusBoxRightClick
    def onPlusBoxRightClick(self, event, p=None):
        if self.busy(): return
        c = self.c
        g.doHook('rclick-popup', c=c, p=p, event=event, context_menu='plusbox')
        c.outerUpdate()
    #@+node:ekr.20110605121601.17891: *4*  qtree.Icon Box
    # For Qt, there seems to be no way to trigger these events.
    #@+node:ekr.20110605121601.17892: *5* qtree.onIconBoxClick
    def onIconBoxClick(self, event, p=None):
        if self.busy(): return
        c = self.c
        g.doHook("iconclick1", c=c, p=p, event=event)
        g.doHook("iconclick2", c=c, p=p, event=event)
        c.outerUpdate()
    #@+node:ekr.20110605121601.17893: *5* qtree.onIconBoxRightClick
    def onIconBoxRightClick(self, event, p=None):
        """Handle a right click in any outline widget."""
        if self.busy(): return
        c = self.c
        g.doHook("iconrclick1", c=c, p=p, event=event)
        g.doHook("iconrclick2", c=c, p=p, event=event)
        c.outerUpdate()
    #@+node:ekr.20110605121601.17894: *5* qtree.onIconBoxDoubleClick
    def onIconBoxDoubleClick(self, event, p=None):
        if self.busy(): return
        c = self.c
        if not p: p = c.p
        if not g.doHook("icondclick1", c=c, p=p, event=event):
            self.endEditLabel()
            self.OnIconDoubleClick(p) # Call the method in the base class.
        g.doHook("icondclick2", c=c, p=p, event=event)
        c.outerUpdate()
    #@+node:ekr.20110605121601.17886: *4* qtree.busy
    def busy(self):
        '''Return True (actually, a debugging string) if any lockout is set.'''
        trace = False
        table = ('contracting','expanding','redrawing','selecting')
        kinds = ','.join([z for z in table if getattr(self, z)])
        if kinds and trace: g.trace(kinds)
        return kinds # Return the string for debugging
    #@+node:ekr.20110605121601.18437: *4* qtree.onContextMenu
    def onContextMenu(self, point):
        c = self.c
        w = self.treeWidget
        handlers = g.tree_popup_handlers
        menu = QtWidgets.QMenu()
        menuPos = w.mapToGlobal(point)
        if not handlers:
            menu.addAction("No popup handlers")
        p = c.p.copy()
        done = set()
        for h in handlers:
            # every handler has to add it's QActions by itself
            if h in done:
                # do not run the same handler twice
                continue
            h(c, p, menu)
        menu.popup(menuPos)
        self._contextmenu = menu
    #@+node:ekr.20110605121601.17912: *4* qtree.onHeadChanged
    # Tricky code: do not change without careful thought and testing.

    def onHeadChanged(self, p, undoType='Typing', s=None, e=None):
        '''Officially change a headline.'''
        trace = False and not g.unitTesting
        trace_hook = True
        verbose = False
        c = self.c; u = c.undoer
        if not p:
            if trace and verbose: g.trace('** no p')
            return
        item = self.getCurrentItem()
        if not item:
            if trace and verbose: g.trace('** no item')
            return
        if not e:
            e = self.getTreeEditorForItem(item)
        if not e:
            if trace and verbose: g.trace('(nativeTree) ** not editing')
            return
        s = g.u(e.text())
        self.closeEditorHelper(e, item)
        oldHead = p.h
        changed = s != oldHead
        if trace and trace_hook:
            g.trace('headkey1: changed %s' % (changed), g.callers())
        if g.doHook("headkey1", c=c, p=c.p, v=c.p, s=s, changed=changed):
            return
        if changed:
            # New in Leo 4.10.1.
            if trace: g.trace('(nativeTree) new', repr(s), 'old', repr(p.h))
            #@+<< truncate s if it has multiple lines >>
            #@+node:ekr.20120409185504.10028: *5* << truncate s if it has multiple lines >>
            # Remove trailing newlines before warning of truncation.
            while s and s[-1] == '\n':
                s = s[: -1]
            # Warn if there are multiple lines.
            i = s.find('\n')
            if i > -1:
                s = s[: i]
                if s != oldHead:
                    g.warning("truncating headline to one line")
            limit = 1000
            if len(s) > limit:
                s = s[: limit]
                if s != oldHead:
                    g.warning("truncating headline to", limit, "characters")
            #@-<< truncate s if it has multiple lines >>
            p.initHeadString(s)
            item.setText(0, s) # Required to avoid full redraw.
            undoData = u.beforeChangeNodeContents(p, oldHead=oldHead)
            if not c.changed: c.setChanged(True)
            # New in Leo 4.4.5: we must recolor the body because
            # the headline may contain directives.
            c.frame.body.recolor(p)
            dirtyVnodeList = p.setDirty()
            u.afterChangeNodeContents(p, undoType, undoData,
                dirtyVnodeList=dirtyVnodeList, inHead=True) # 2013/08/26.
        g.doHook("headkey2", c=c, p=c.p, v=c.p, s=s, changed=changed)
        # This is a crucial shortcut.
        if g.unitTesting: return
        if changed:
            self.redraw_after_head_changed()
        if 0: # Don't do this: it interferes with clicks, and is not needed.
            if self.stayInTree:
                c.treeWantsFocus()
            else:
                c.bodyWantsFocus()
        p.v.contentModified()
        c.outerUpdate()
    #@+node:ekr.20110605121601.17896: *4* qtree.onItemClicked
    def onItemClicked(self, item, col, auto_edit=False):
        '''Handle a click in a BaseNativeTree widget item.'''
        # This is called after an item is selected.
        trace = False and not g.unitTesting
        if self.busy(): return
        c = self.c
        # if trace: g.trace(self.traceItem(item),g.callers(4))
        try:
            self.selecting = True
            p = self.item2position(item)
            auto_edit = self.prev_v == p.v
            if p:
                self.prev_v = p.v
                event = None
                mods = g.app.gui.qtApp.keyboardModifiers()
                isCtrl = bool(mods & QtConst.ControlModifier)
                if trace: g.trace('auto_edit', auto_edit, 'ctrl', isCtrl, p.h)
                # We could also add support for QtConst.ShiftModifier, QtConst.AltModifier	& QtConst.MetaModifier.
                if isCtrl:
                    if g.doHook("iconctrlclick1", c=c, p=p, event=event) is None:
                        c.frame.tree.OnIconCtrlClick(p) # Call the base class method.
                    g.doHook("iconctrlclick2", c=c, p=p, event=event)
                else:
                    # 2014/02/21: generate headclick1/2 instead of iconclick1/2
                    g.doHook("headclick1", c=c, p=p, event=event)
                    g.doHook("headclick2", c=c, p=p, event=event)
            else:
                auto_edit = None
                g.trace('*** no p')
            # 2011/05/27: click here is like ctrl-g.
            c.k.keyboardQuit(setFocus=False)
            c.treeWantsFocus() # 2011/05/08: Focus must stay in the tree!
            c.outerUpdate()
            # 2011/06/01: A second *single* click on a selected node
            # enters editing state.
            if auto_edit and self.auto_edit:
                e, wrapper = self.createTreeEditorForItem(item)
            # 2014/10/26: Reset find vars.
            c.findCommands.reset_state_ivars()
        finally:
            self.selecting = False
    #@+node:ekr.20110605121601.17895: *4* qtree.onItemCollapsed
    def onItemCollapsed(self, item):
        trace = False
        if self.busy(): return
        c = self.c
        if trace: g.trace(self.traceItem(item))
        p = self.item2position(item)
        if p:
            # Important: do not set lockouts here.
            # Only methods that actually generate events should set lockouts.
            p.contract()
            if p.isCloned():
                self.select(p) # Calls before/afterSelectHint.
                # 2010/02/04: Keep the expansion bits of all tree nodes in sync.
                self.full_redraw(scroll=False)
            else:
                self.select(p) # Calls before/afterSelectHint.
        else:
            self.error('no p')
        c.outerUpdate()
    #@+node:ekr.20110605121601.17897: *4* qtree.onItemDoubleClicked
    def onItemDoubleClicked(self, item, col):
        '''Handle a double click in a BaseNativeTree widget item.'''
        trace = False and not g.unitTesting
        if self.busy(): return
        c = self.c
        if trace: g.trace(col, self.traceItem(item))
        try:
            self.selecting = True
            e, wrapper = self.createTreeEditorForItem(item)
            if not e:
                g.trace('*** no e')
            p = self.item2position(item)
        # 2011/07/28: End the lockout here, not at the end.
        finally:
            self.selecting = False
        if p:
            # 2014/02/21: generate headddlick1/2 instead of icondclick1/2.
            event = None
            if g.doHook("headdclick1", c=c, p=p, event=event) is None:
                c.frame.tree.OnIconDoubleClick(p) # Call the base class method.
            g.doHook("headclick2", c=c, p=p, event=event)
        else:
            g.trace('*** no p')
        c.outerUpdate()
    #@+node:ekr.20110605121601.17898: *4* qtree.onItemExpanded
    def onItemExpanded(self, item):
        '''Handle and tree-expansion event.'''
        trace = False
        if self.busy(): return
        c = self.c
        if trace: g.trace(self.traceItem(item))
        p = self.item2position(item)
        if p:
            # Important: do not set lockouts here.
            # Only methods that actually generate events should set lockouts.
            if not p.isExpanded():
                p.expand()
                self.select(p) # Calls before/afterSelectHint.
                # Important: setting scroll=False here has no effect
                # when a keystroke causes the expansion, but is a
                # *big* improvement when clicking the outline.
                self.full_redraw(scroll=False)
            else:
                self.select(p)
        else:
            self.error('no p')
        c.outerUpdate()
    #@+node:ekr.20110605121601.17899: *4* qtree.onTreeSelect
    def onTreeSelect(self):
        '''Select the proper position when a tree node is selected.'''
        trace = False and not g.unitTesting
        if self.busy(): return
        c = self.c
        item = self.getCurrentItem()
        p = self.item2position(item)
        if p:
            # Important: do not set lockouts here.
            # Only methods that actually generate events should set lockouts.
            if trace: g.trace(self.traceItem(item))
            self.select(p)
                # This is a call to LeoTree.select(!!)
                # Calls before/afterSelectHint.
        else:
            self.error('no p for item: %s' % item)
        c.outerUpdate()
    #@+node:ekr.20110605121601.17900: *4* qtree.OnPopup & allies
    def OnPopup(self, p, event):
        """Handle right-clicks in the outline.

        This is *not* an event handler: it is called from other event handlers."""
        # Note: "headrclick" hooks handled by VNode callback routine.
        if event:
            c = self.c
            c.setLog()
            if not g.doHook("create-popup-menu", c=c, p=p, event=event):
                self.createPopupMenu(event)
            if not g.doHook("enable-popup-menu-items", c=c, p=p, event=event):
                self.enablePopupMenuItems(p, event)
            if not g.doHook("show-popup-menu", c=c, p=p, event=event):
                self.showPopupMenu(event)
        return "break"
    #@+node:ekr.20110605121601.17901: *5* qtree.OnPopupFocusLost
    #@+at
    # On Linux we must do something special to make the popup menu "unpost" if the
    # mouse is clicked elsewhere. So we have to catch the <FocusOut> event and
    # explicitly unpost. In order to process the <FocusOut> event, we need to be able
    # to find the reference to the popup window again, so this needs to be an
    # attribute of the tree object; hence, "self.popupMenu".
    # 
    # Aside: though Qt tries to be muli-platform, the interaction with different
    # window managers does cause small differences that will need to be compensated by
    # system specific application code. :-(
    #@@c
    # 20-SEP-2002 DTHEIN: This event handler is only needed for Linux.

    def OnPopupFocusLost(self, event=None):
        # self.popupMenu.unpost()
        pass
    #@+node:ekr.20110605121601.17902: *5* qtree.createPopupMenu
    def createPopupMenu(self, event):
        '''This might be a placeholder for plugins.  Or not :-)'''
    #@+node:ekr.20110605121601.17903: *5* qtree.enablePopupMenuItems
    def enablePopupMenuItems(self, p, event):
        """Enable and disable items in the popup menu."""
    #@+node:ekr.20110605121601.17904: *5* qtree.showPopupMenu
    def showPopupMenu(self, event):
        """Show a popup menu."""
    #@+node:ekr.20110605121601.17944: *3* qtree.Focus
    def getFocus(self):
        return g.app.gui.get_focus(self.c) # Bug fix: 2009/6/30

    findFocus = getFocus

    def setFocus(self):
        g.app.gui.set_focus(self.c, self.treeWidget)
    #@+node:ekr.20110605121601.18409: *3* qtree.Icons
    #@+node:ekr.20110605121601.18410: *4* qtree.drawIcon
    def drawIcon(self, p):
        '''Redraw the icon at p.'''
        w = self.treeWidget
        itemOrTree = self.position2item(p) or w
        item = QtWidgets.QTreeWidgetItem(itemOrTree)
        icon = self.getIcon(p)
        self.setItemIcon(item, icon)
    #@+node:ekr.20110605121601.17946: *4* qtree.drawItemIcon
    def drawItemIcon(self, p, item):
        '''Set the item's icon to p's icon.'''
        icon = self.getIcon(p)
        if icon:
            self.setItemIcon(item, icon)
    #@+node:ekr.20110605121601.18411: *4* qtree.getIcon & helper
    def getIcon(self, p):
        '''Return the proper icon for position p.'''
        p.v.iconVal = val = p.v.computeIcon()
        return self.getCompositeIconImage(p, val)
    #@+node:ekr.20110605121601.18412: *5* qtree.getCompositeIconImage
    def getCompositeIconImage(self, p, val):
        '''Get the icon at position p.'''
        trace = False and not g.unitTesting
        trace_cached = False
        userIcons = self.c.editCommands.getIconList(p)
        # don't take this shortcut - not theme aware, see getImageImage()
        # which is called below - TNB 20130313
        # if not userIcons:
        #     # if trace: g.trace('no userIcons')
        #     return self.getStatusIconImage(p)
        hash = [i['file'] for i in userIcons if i['where'] == 'beforeIcon']
        hash.append(str(val))
        hash.extend([i['file'] for i in userIcons if i['where'] == 'beforeHeadline'])
        hash = ':'.join(hash)
        if hash in g.app.gui.iconimages:
            icon = g.app.gui.iconimages[hash]
            if trace and trace_cached: g.trace('cached %s' % (icon))
            return icon
        images = [g.app.gui.getImageImage(i['file']) for i in userIcons
                 if i['where'] == 'beforeIcon']
        images.append(g.app.gui.getImageImage("box%02d.png" % val))
        images.extend([g.app.gui.getImageImage(i['file']) for i in userIcons
                      if i['where'] == 'beforeHeadline'])
        images = [z for z in images if z] # 2013/12/23: Remove missing images.
        if not images:
            return None
        hsep = self.c.config.getInt('tree-icon-separation') or 0
        width = sum([i.width() for i in images]) + hsep * (len(images)-1)
        height = max([i.height() for i in images])
        pix = QtGui.QImage(width, height, QtGui.QImage.Format_ARGB32_Premultiplied)
        pix.fill(QtGui.QColor(0, 0, 0, 0).rgba()) # transparent fill, rgbA
        # .rgba() call required for Qt4.7, later versions work with straight color
        painter = QtGui.QPainter()
        if not painter.begin(pix):
            print("Failed to init. painter for icon")
            # don't return, the code still makes an icon for the cache
            # which stops this being called again and again
        x = 0
        for i in images:
            painter.drawPixmap(x, (height - i.height()) // 2, i)
            x += i.width() + hsep
        painter.end()
        icon = QtGui.QIcon(QtGui.QPixmap.fromImage(pix))
        g.app.gui.iconimages[hash] = icon
        if trace: g.trace('new %s' % (icon))
        return icon
    #@+node:ekr.20110605121601.17947: *4* qtree.getIconImage
    def getIconImage(self, p):
        # User icons are not supported in the base class.
        if g.app.gui.isNullGui:
            return None
        else:
            return self.getStatusIconImage(p)
    #@+node:ekr.20110605121601.17948: *4* qtree.getStatusIconImage
    def getStatusIconImage(self, p):
        val = p.v.computeIcon()
        r = g.app.gui.getIconImage(
            "box%02d.png" % val)
        # g.trace(r)
        return r
    #@+node:ekr.20110605121601.17949: *4* qtree.getVnodeIcon
    def getVnodeIcon(self, p):
        '''Return the proper icon for position p.'''
        return self.getIcon(p)
    #@+node:ekr.20110605121601.17950: *4* qtree.setItemIcon
    def setItemIcon(self, item, icon):
        trace = False and not g.unitTesting
        valid = item and self.isValidItem(item)
        if icon and valid:
            # Important: do not set lockouts here.
            # This will generate changed events,
            # but there is no itemChanged event handler.
            self.setItemIconHelper(item, icon)
        elif trace:
            # Apparently, icon can be None due to recent icon changes.
            if icon:
                g.trace('** item %s, valid: %s, icon: %s' % (
                    item and id(item) or '<no item>', valid, icon),
                    g.callers(4))
    #@+node:ekr.20110605121601.18413: *4* qtree.setItemIconHelper
    def setItemIconHelper(self, item, icon):
        # Generates an item-changed event.
        # g.trace(id(icon))
        if item:
            item.setIcon(0, icon)
    #@+node:ekr.20110605121601.17951: *4* qtree.updateIcon
    def updateIcon(self, p, force=False):
        '''Update p's icon.'''
        if not p: return
        val = p.v.computeIcon()
        # The force arg is needed:
        # Leo's core may have updated p.v.iconVal.
        if p.v.iconVal == val and not force:
            return
        icon = self.getIcon(p) # sets p.v.iconVal
        # Update all cloned items.
        items = self.vnode2items(p.v)
        for item in items:
            self.setItemIcon(item, icon)
    #@+node:ekr.20110605121601.17952: *4* qtree.updateVisibleIcons
    def updateVisibleIcons(self, p):
        '''Update the icon for p and the icons
        for all visible descendants of p.'''
        self.updateIcon(p, force=True)
        if p.hasChildren() and p.isExpanded():
            for child in p.children():
                self.updateVisibleIcons(child)
    #@+node:ekr.20110605121601.18414: *3* qtree.Items
    #@+node:ekr.20110605121601.17943: *4*  qtree.item dict getters
    def itemHash(self, item):
        return '%s at %s' % (repr(item), str(id(item)))

    def item2position(self, item):
        itemHash = self.itemHash(item)
        p = self.item2positionDict.get(itemHash) # was item
        # g.trace(item,p.h)
        return p

    def item2vnode(self, item):
        itemHash = self.itemHash(item)
        return self.item2vnodeDict.get(itemHash) # was item

    def position2item(self, p):
        item = self.position2itemDict.get(p.key())
        return item

    def vnode2items(self, v):
        return self.vnode2itemsDict.get(v, [])

    def isValidItem(self, item):
        itemHash = self.itemHash(item)
        return itemHash in self.item2vnodeDict # was item.
    #@+node:ekr.20110605121601.18415: *4* qtree.childIndexOfItem
    def childIndexOfItem(self, item):
        parent = item and item.parent()
        if parent:
            n = parent.indexOfChild(item)
        else:
            w = self.treeWidget
            n = w.indexOfTopLevelItem(item)
        return n
    #@+node:ekr.20110605121601.18416: *4* qtree.childItems
    def childItems(self, parent_item):
        '''Return the list of child items of the parent item,
        or the top-level items if parent_item is None.'''
        if parent_item:
            n = parent_item.childCount()
            items = [parent_item.child(z) for z in range(n)]
        else:
            w = self.treeWidget
            n = w.topLevelItemCount()
            items = [w.topLevelItem(z) for z in range(n)]
        return items
    #@+node:ekr.20110605121601.18417: *4* qtree.closeEditorHelper
    def closeEditorHelper(self, e, item):
        'End editing of the underlying QLineEdit widget for the headline.' ''
        w = self.treeWidget
        if e:
            w.closeEditor(e, QtWidgets.QAbstractItemDelegate.NoHint)
            try:
                # work around https://bugs.launchpad.net/leo-editor/+bug/1041906
                # underlying C/C++ object has been deleted
                w.setItemWidget(item, 0, None)
                    # Make sure e is never referenced again.
                w.setCurrentItem(item)
            except RuntimeError:
                if 1: # Testing.
                    g.es_exception()
                else:
                    # Recover silently even if there is a problem.
                    pass
    #@+node:ekr.20110605121601.18418: *4* qtree.connectEditorWidget & helper
    def connectEditorWidget(self, e, item):
        if not e:
            return g.trace('can not happen: no e')
        # Hook up the widget.
        wrapper = self.getWrapper(e, item)

        def editingFinishedCallback(e=e, item=item, self=self, wrapper=wrapper):
            # g.trace(wrapper,g.callers(5))
            c = self.c
            w = self.treeWidget
            self.onHeadChanged(p=c.p, e=e)
            w.setCurrentItem(item)

        e.editingFinished.connect(editingFinishedCallback)
        return wrapper # 2011/02/12
    #@+node:ekr.20110605121601.18419: *4* qtree.contractItem & expandItem
    def contractItem(self, item):
        # g.trace(g.callers(4))
        self.treeWidget.collapseItem(item)

    def expandItem(self, item):
        # g.trace(g.callers(4))
        self.treeWidget.expandItem(item)
    #@+node:ekr.20110605121601.18420: *4* qtree.createTreeEditorForItem
    def createTreeEditorForItem(self, item):
        trace = False and not g.unitTesting
        w = self.treeWidget
        w.setCurrentItem(item) # Must do this first.
        if self.use_declutter:
            item.setText(0, item._real_text)
        w.editItem(item)
        e = w.itemWidget(item, 0)
        e.setObjectName('headline')
        wrapper = self.connectEditorWidget(e, item)
        if trace: g.trace(e, wrapper)
        self.sizeTreeEditor(self.c, e)
        return e, wrapper
    #@+node:ekr.20110605121601.18421: *4* qtree.createTreeItem
    def createTreeItem(self, p, parent_item):
        trace = False and not g.unitTesting
        w = self.treeWidget
        itemOrTree = parent_item or w
        item = QtWidgets.QTreeWidgetItem(itemOrTree)
        item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
        if trace: g.trace(id(item), p.h, g.callers(4))
        try:
            g.visit_tree_item(self.c, p, item)
        except leoPlugins.TryNext:
            pass
        #print "item",item
        return item
    #@+node:ekr.20110605121601.18422: *4* qtree.editLabelHelper
    def editLabelHelper(self, item, selectAll=False, selection=None):
        '''
        Help nativeTree.editLabel do gui-specific stuff.
        '''
        c, vc = self.c, self.c.vimCommands
        w = self.treeWidget
        w.setCurrentItem(item)
            # Must do this first.
            # This generates a call to onTreeSelect.
        w.editItem(item)
            # Generates focus-in event that tree doesn't report.
        e = w.itemWidget(item, 0) # A QLineEdit.
        if e:
            s = e.text(); len_s = len(s)
            if s == 'newHeadline': selectAll = True
            if selection:
                # pylint: disable=unpacking-non-sequence
                # Fix bug https://groups.google.com/d/msg/leo-editor/RAzVPihqmkI/-tgTQw0-LtwJ
                # Note: negative lengths are allowed.
                i, j, ins = selection
                if ins is None:
                    start, n = i, abs(i - j)
                    # This case doesn't happen for searches.
                elif ins == j:
                    start, n = i, j - i
                else:
                    start = start, n = j, i - j
                # g.trace('i',i,'j',j,'ins',ins,'-->start',start,'n',n)
            elif selectAll: start, n, ins = 0, len_s, len_s
            else: start, n, ins = len_s, 0, len_s
            e.setObjectName('headline')
            e.setSelection(start, n)
            # e.setCursorPosition(ins) # Does not work.
            e.setFocus()
            wrapper = self.connectEditorWidget(e, item) # Hook up the widget.
            if vc and c.vim_mode: #  and selectAll
                # For now, *always* enter insert mode.
                if vc.is_text_wrapper(wrapper):
                    vc.begin_insert_mode(w=wrapper)
                else:
                    g.trace('not a text widget!', wrapper)
        return e, wrapper
    #@+node:ekr.20110605121601.18423: *4* qtree.getCurrentItem
    def getCurrentItem(self):
        w = self.treeWidget
        return w.currentItem()
    #@+node:ekr.20110605121601.18424: *4* qtree.getItemText
    def getItemText(self, item):
        '''Return the text of the item.'''
        if item:
            return g.u(item.text(0))
        else:
            return '<no item>'
    #@+node:ekr.20110605121601.18425: *4* qtree.getParentItem
    def getParentItem(self, item):
        return item and item.parent()
    #@+node:ekr.20110605121601.18426: *4* qtree.getSelectedItems
    def getSelectedItems(self):
        w = self.treeWidget
        return w.selectedItems()
    #@+node:ekr.20110605121601.18427: *4* qtree.getTreeEditorForItem
    def getTreeEditorForItem(self, item):
        '''Return the edit widget if it exists.
        Do *not* create one if it does not exist.'''
        trace = False and not g.unitTesting
        w = self.treeWidget
        e = w.itemWidget(item, 0)
        if trace and e: g.trace(e.__class__.__name__)
        return e
    #@+node:ekr.20110605121601.18428: *4* qtree.getWrapper
    def getWrapper(self, e, item):
        '''Return headlineWrapper that wraps e (a QLineEdit).'''
        trace = False and not g.unitTesting
        c = self.c
        if e:
            wrapper = self.editWidgetsDict.get(e)
            if wrapper:
                pass # g.trace('old wrapper',e,wrapper)
            else:
                if item:
                    # 2011/02/12: item can be None.
                    wrapper = self.headlineWrapper(c, item, name='head', widget=e)
                    if trace: g.trace('new wrapper', e, wrapper)
                    self.editWidgetsDict[e] = wrapper
                else:
                    if trace: g.trace('no item and no wrapper',
                        e, self.editWidgetsDict)
            return wrapper
        else:
            g.trace('no e')
            return None
    #@+node:ekr.20110605121601.18429: *4* qtree.nthChildItem
    def nthChildItem(self, n, parent_item):
        children = self.childItems(parent_item)
        if n < len(children):
            item = children[n]
        else:
            # This is **not* an error.
            # It simply means that we need to redraw the tree.
            item = None
        return item
    #@+node:ekr.20110605121601.18430: *4* qtree.scrollToItem
    def scrollToItem(self, item):
        w = self.treeWidget
        # g.trace(self.traceItem(item))
        hPos, vPos = self.getScroll()
        w.scrollToItem(item, w.EnsureVisible)
            # Fix #265: Erratic scrolling bug.
            # w.PositionAtCenter causes unwanted scrolling.
        self.setHScroll(0)
            # Necessary
    #@+node:ekr.20110605121601.18431: *4* qtree.setCurrentItemHelper
    def setCurrentItemHelper(self, item):
        w = self.treeWidget
        w.setCurrentItem(item)
    #@+node:ekr.20110605121601.18432: *4* qtree.setItemText
    def setItemText(self, item, s):
        if item:
            item.setText(0, s)
            if self.use_declutter:
                item._real_text = s
    #@+node:tbrown.20160406221505.1: *4* qtree.sizeTreeEditor
    @staticmethod
    def sizeTreeEditor(c, editor):
        """Size a QLineEdit in a tree headline so scrolling occurs"""
        # space available in tree widget
        space = c.frame.tree.treeWidget.size().width()
        # left hand edge of editor within tree widget
        used = editor.geometry().x() + 4  # + 4 for edit cursor
        # limit width to available space
        editor.resize(space - used, editor.size().height())
    #@+node:ekr.20110605121601.18433: *3* qtree.Scroll bars
    #@+node:ekr.20110605121601.18434: *4* qtree.getSCroll
    def getScroll(self):
        '''Return the hPos,vPos for the tree's scrollbars.'''
        w = self.treeWidget
        hScroll = w.horizontalScrollBar()
        vScroll = w.verticalScrollBar()
        hPos = hScroll.sliderPosition()
        vPos = vScroll.sliderPosition()
        return hPos, vPos
    #@+node:btheado.20111110215920.7164: *4* qtree.scrollDelegate
    def scrollDelegate(self, kind):
        '''Scroll a QTreeWidget up or down or right or left.
        kind is in ('down-line','down-page','up-line','up-page', 'right', 'left')
        '''
        c = self.c; w = self.treeWidget
        if kind in ('left', 'right'):
            hScroll = w.horizontalScrollBar()
            if kind == 'right':
                delta = hScroll.pageStep()
            else:
                delta = -hScroll.pageStep()
            hScroll.setValue(hScroll.value() + delta)
        else:
            vScroll = w.verticalScrollBar()
            h = w.size().height()
            lineSpacing = w.fontMetrics().lineSpacing()
            n = h / lineSpacing
            if kind == 'down-half-page': delta = n / 2
            elif kind == 'down-line': delta = 1
            elif kind == 'down-page': delta = n
            elif kind == 'up-half-page': delta = -n / 2
            elif kind == 'up-line': delta = -1
            elif kind == 'up-page': delta = -n
            else:
                delta = 0; g.trace('bad kind:', kind)
            val = vScroll.value()
            # g.trace(kind,n,h,lineSpacing,delta,val)
            vScroll.setValue(val + delta)
        c.treeWantsFocus()
    #@+node:ekr.20110605121601.18435: *4* qtree.setH/VScroll
    def setHScroll(self, hPos):
        w = self.treeWidget
        hScroll = w.horizontalScrollBar()
        hScroll.setValue(hPos)

    def setVScroll(self, vPos):
        # g.trace(vPos)
        w = self.treeWidget
        vScroll = w.verticalScrollBar()
        vScroll.setValue(vPos)
    #@+node:ekr.20110605121601.17905: *3* qtree.Selecting & editing
    #@+node:ekr.20110605121601.17906: *4* qtree.afterSelectHint
    def afterSelectHint(self, p, old_p):
        trace = False and not g.unitTesting
        c = self.c
        if c.enableRedrawFlag:
            self.selecting = False
            if self.busy():
                self.error('afterSelectHint busy!: %s' % self.busy())
            if not p:
                return self.error('no p')
            if p != c.p:
                if trace: self.error(
                    '(afterSelectHint) p != c.p\np:   %s\nc.p: %s\n' % (
                    repr(p), repr(c.currentPosition())))
                p = c.p
            # if trace: g.trace(c.p.h,g.callers())
            # We don't redraw during unit testing: an important speedup.
            if c.expandAllAncestors(p) and not g.unitTesting:
                if trace: g.trace('***self.full_redraw')
                self.full_redraw(p)
            else:
                if trace: g.trace('*** c.outerUpdate')
                c.outerUpdate() # Bring the tree up to date.
                self.setItemForCurrentPosition(scroll=False)
        else:
            self.selecting = False
            c.requestLaterRedraw = True
    #@+node:ekr.20110605121601.17907: *4* qtree.beforeSelectHint
    def beforeSelectHint(self, p, old_p):
        trace = False and not g.unitTesting
        if self.busy(): return
        c = self.c
        if trace: g.trace(p and p.h, c.p.h)
        # Disable onTextChanged.
        self.selecting = True
        self.prev_v = c.p.v
    #@+node:ekr.20110605121601.17908: *4* qtree.edit_widget
    def edit_widget(self, p):
        """Returns the edit widget for position p."""
        trace = False and not g.unitTesting
        verbose = False
        # if False and g.unitTesting:
            # ### Highly experimental: 10 unit tests fail.
            # return HeadWrapper(c=self.c, name='head', p=p)
        item = self.position2item(p)
        if item:
            e = self.getTreeEditorForItem(item)
            if e:
                # Create a wrapper widget for Leo's core.
                w = self.getWrapper(e, item)
                if trace: g.trace(w, p and p.h)
                return w
            else:
                # This is not an error
                # But warning: calling this method twice might not work!
                if trace and verbose: g.trace('no e for %s' % (p))
                return None
        else:
            if trace and verbose: self.error('no item for %s' % (p))
            return None
    #@+node:ekr.20110605121601.17909: *4* qtree.editLabel
    def editLabel(self, p, selectAll=False, selection=None):
        """Start editing p's headline."""
        trace = False and not g.unitTesting
        if self.busy():
            if trace: g.trace('busy')
            return
        c = self.c
        c.outerUpdate()
            # Do any scheduled redraw.
            # This won't do anything in the new redraw scheme.
        item = self.position2item(p)
        if item:
            if self.use_declutter:
                item.setText(0, item._real_text)
            e, wrapper = self.editLabelHelper(item, selectAll, selection)
        else:
            e, wrapper = None, None
            self.error('no item for %s' % p)
        if trace: g.trace('p: %s e: %s' % (p and p.h, e))
        if e:
            self.sizeTreeEditor(c, e)
            # A nice hack: just set the focus request.
            c.requestedFocusWidget = e
        return e, wrapper
    #@+node:ekr.20110605121601.17910: *4* qtree.editPosition (no longer used)
    # def editPosition(self):
        # c = self.c
        # p = c.currentPosition()
        # ew = self.edit_widget(p)
        # return p if ew else None
    #@+node:ekr.20110605121601.17911: *4* qtree.endEditLabel
    def endEditLabel(self):
        '''Override LeoTree.endEditLabel.

        End editing of the presently-selected headline.'''
        c = self.c; p = c.currentPosition()
        self.onHeadChanged(p)
    #@+node:ekr.20110605121601.17915: *4* qtree.getSelectedPositions
    def getSelectedPositions(self):
        items = self.getSelectedItems()
        pl = leoNodes.PosList(self.item2position(it) for it in items)
        return pl
    #@+node:ekr.20110605121601.17914: *4* qtree.setHeadline
    def setHeadline(self, p, s):
        '''Force the actual text of the headline widget to p.h.'''
        trace = False and not g.unitTesting
        # This is used by unit tests to force the headline and p into alignment.
        if not p:
            if trace: g.trace('*** no p')
            return
        # Don't do this here: the caller should do it.
        # p.setHeadString(s)
        e = self.edit_widget(p)
        if e:
            if trace: g.trace('e', s)
            e.setAllText(s)
        else:
            item = self.position2item(p)
            if item:
                if trace: g.trace('item', s)
                self.setItemText(item, s)
            else:
                if trace: g.trace('*** failed. no item for %s' % p.h)
    #@+node:ekr.20110605121601.17913: *4* qtree.setItemForCurrentPosition
    def setItemForCurrentPosition(self, scroll=True):
        '''Select the item for c.p'''
        trace = False and not g.unitTesting
        verbose = True
        c = self.c; p = c.currentPosition()
        if self.busy():
            if trace and verbose: g.trace('** busy')
            return None
        if not p:
            if trace and verbose: g.trace('** no p')
            return None
        item = self.position2item(p)
        if not item:
            # This is not necessarily an error.
            # We often attempt to select an item before redrawing it.
            if trace and verbose:
                g.trace('** no item for', p)
                g.trace(g.callers())
            return None
        item2 = self.getCurrentItem()
        if item == item2:
            if trace and verbose: g.trace('no change', self.traceItem(item), p.h)
            if scroll:
                self.scrollToItem(item)
        else:
            try:
                self.selecting = True
                # This generates gui events, so we must use a lockout.
                if trace and verbose: g.trace('setCurrentItem', self.traceItem(item), p.h)
                self.setCurrentItemHelper(item)
                    # Just calls self.setCurrentItem(item)
                if scroll:
                    if trace: g.trace(self.traceItem(item))
                    self.scrollToItem(item)
            finally:
                self.selecting = False
        # if trace: g.trace('item',repr(item))
        if not item: g.trace('*** no item')
        return item
    #@-others
#@-others
#@@language python
#@@tabwidth -4
#@@pagewidth 80
#@-leo
