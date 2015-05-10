#!/usr/bin/env python

import curses, sys
import curses.textpad as textpad
import os
import locale
from time import time
import textwrap

SECS_IN_DAY = 60 * 60 * 24

OLD_AGE_DAYS = 7
START_Y = 2
START_X = 4

def load_categories(data, path):
    position = [(data, -2)]

    for filename in os.listdir(path):
        section = [([filename], -1)] + [(line.strip().split('@@@'), len(line) - len(line.lstrip())) for line in open(path + filename)]
        for (caption, indent) in section:
            if caption[0] == '':
                continue
            while position[-1][1] > indent:
                position.pop()
            #time, expanded, marked = [''] * 3
            time, expanded, marked = caption[-1].split(',') if len(caption) > 1 else [''] * 3
            item = dict(caption = caption[0], time = int(time) if time.isdigit() else None, hover = False, expanded = expanded == 'e', marked = marked == 'm', items = [])
            if position[-1][1] == indent:
                position[-2][0]['items'].append(item)
                position.pop()
            else:
                position[-1][0]['items'].append(item)
            position.append((item, indent))

def save_category(path, data, position):
    if data['items']:
        (founder, founder_index) = position[0]
        category = founder['items'][founder_index]
        f = open(path + category['caption'], 'w+')
        do_save_category(category, f, 0)

def do_save_category(category, f, indent):
    for item in category['items']:
        f.write('    ' * indent + item['caption'] + '@@@' + ','.join([str(item['time'] if item['time'] else ''), 'e' if item['expanded'] else '', 'm' if item['marked'] else '']) + '\n')
        do_save_category(item, f, indent + 1)

def caption_str(section):
    s = ''
    if section['items']:
        s += '[-] ' if section['expanded'] else '[+] '
    s += section['caption']
    return s

def time_str(section):
    s = ''
    c = 0
    if section['time']:
        time_diff = int(time()) - section['time']
        if time_diff > SECS_IN_DAY:
            s += ' ('
            s += str(time_diff / SECS_IN_DAY) + 'd'
            s += ')'
            c = 3 if time_diff > SECS_IN_DAY * OLD_AGE_DAYS else 2
    return (s, c)

def unfold_section(screen, section, pos_y, pos_x, root = True, column_x = START_X):
    max_y, max_x = screen.getmaxyx()
    for item in section['items']:
        caption = caption_str(item)
        caption = textwrap.wrap(caption_str(item), 80 - 4 - pos_x)

        if item['hover']:
            global edit_y, edit_x
            edit_y = pos_y
            edit_x = column_x + pos_x + (4 if item['items'] else 0)
        if item['caption'] == '':
            global write_y, write_x
            write_y = pos_y
            write_x = column_x + pos_x
            pos_y += 1

        first = True
        for line in caption:
            if pos_y >= max_y - 5:
                column_x += 80 + START_X
                pos_y = START_Y
            if column_x + pos_x + len(line) >= max_x - START_X:
                line =  line[:max_x - START_X - column_x - pos_x - 3] + '...'

            color = curses.color_pair(0)
            if item['hover']:
                color = curses.A_REVERSE
            elif item['marked']:
                color = curses.color_pair(1)

            screen.addstr(pos_y, column_x + pos_x, line, color)
            pos_y += 1
            if first and len(caption) > 1:
                pos_x += 4
                first = False

        (time, time_color) = time_str(item)
        if time != '':
            # error: this might bug, going outside y boundaries
            if len(caption[-1]) + len(time) <= 80:
                screen.addstr(pos_y - 1, column_x + pos_x + len(caption[-1]), time, curses.color_pair(time_color))
            else:
                screen.addstr(pos_y, column_x + pos_x, time, curses.color_pair(time_color))
                pos_y += 1

        if not first:
            pos_x -= 4

        if item['expanded']:
            pos_y, pos_x, column_x = unfold_section(screen, item, pos_y, pos_x + START_X, False, column_x)
            pos_x -= START_X
        if root:
            pos_y += 1

    return pos_y, pos_x, column_x

def draw(screen, data):
    screen.erase()
    #unfold_section(screen, data, START_Y, 0)
    unfold_section(screen, position[zoom_level][0], START_Y, 0)
    #screen.addstr(58, 4, '   ::   '.join(['[]' if not p['items'] else p['items'][i]['caption'] + ' (' + str(i) + ', E' + ('+' if p['items'][i]['expanded'] else '-') + ', U' + ('+' if p['items'][i]['marked'] else '-') + ')' for (p, i) in position]))
    _, max_x = screen.getmaxyx()
    #screen.addstr(59, 4, str(len(data['items'])))
    screen.refresh()

def move_up(parent, index, position):
    new_index = index - 1 if index > 0 else len(parent['items']) - 1
    parent['items'][index]['hover'] = False
    parent['items'][new_index]['hover'] = True
    position.pop()
    position.append((parent, new_index))

def move_down(parent, index, position):
    new_index = index + 1 if len(parent['items']) - 1 > index else 0
    parent['items'][index]['hover'] = False
    parent['items'][new_index]['hover'] = True
    position.pop()
    position.append((parent, new_index))

def move_left(parent, self, position):
    if len(position) > 1:
        self['hover'] = False
        parent['hover'] = True
        position.pop()

def move_right(self, position):
    if self and self['items']:
        self['hover'] = False
        self['items'][0]['hover'] = True
        self['expanded'] = True
        position.append((self, 0))

def flip_expansion(self):
    if self:
        self['expanded'] = not self['expanded']

def flip_recursively(self, state):
    self['expanded'] = state
    for idx in range(len(self['items'])):
        flip_recursively(self['items'][idx], state)

def delete(parent, index, position):
    if len(parent['items']) - 1 > index:
        del parent['items'][index]
        parent['items'][index]['hover'] = True
    elif index != 0:
        del parent['items'][index]
        parent['items'][index - 1]['hover'] = True
        position.pop()
        position.append((parent, index - 1))
    elif len(position) > 1:
        del parent['items'][index]
        position.pop()
        (grandparent, grandindex) = position[-1]
        grandparent['items'][grandindex]['hover'] = True
    else:
        position[0][0]['items'] = []

def add_sibling(parent, index, below, position):
    parent['items'].insert(index + below, dict(caption = '', time = int(time()), hover = False, expanded = False, marked = False, items = []))
    draw(screen, data)
    screen.addstr(write_y, write_x - 4, '--> ')
    curses.echo()
    caption = screen.getstr(write_y, write_x).strip()
    curses.noecho()
    if caption == '':
        del parent['items'][index + below]
    else:
        parent['items'][index + below]['caption'] = caption
        if below:
            move_down(parent, index, position)
        else:
            parent['items'][index]['hover'] = True
            if len(parent['items']) > 1:
                parent['items'][index + 1]['hover'] = False

def add_child(parent, index, position):
    self = parent['items'][index]
    self['items'].insert(0, dict(caption = '', time = int(time()), hover = False, expanded = False, marked = False, items = []))
    self['expanded'] = True
    draw(screen, data)
    screen.addstr(write_y, write_x - 4, '--> ')
    curses.echo()
    caption = screen.getstr(write_y, write_x).strip()
    curses.noecho()
    if caption == '':
        del self['items'][0]
    else:
        self['items'][0]['caption'] = caption
        move_right(self, position)

def paste(parent, index, item, below, position):
    parent['items'].insert(index + below, item)
    parent['items'][index]['hover'] = True
    if below:
        parent['items'][index]['hover'] = False
        parent['items'][index + 1]['hover'] = True
        position[-1] = (parent, index + 1)
    else:
        parent['items'][index]['hover'] = True
        if len(parent['items']) > 1:
            parent['items'][index + 1]['hover'] = False

def edit_caption(self):
    if not self:
        return
    screen.addstr(edit_y, edit_x - 4, '--> ')
    curses.echo()
    caption = screen.getstr(edit_y, edit_x).strip()
    curses.noecho()
    if caption != '':
        self['caption'] = caption

def flip_marked(self):
    if self:
        self['marked'] = not self['marked']

def update_time(self):
    if self:
        self['time'] = int(time())

locale.setlocale(locale.LC_ALL, '')
path = './todo/'

data = dict(items = [])
load_categories(data, path)

deleted = []
zoom_level = 0

position = [(data, 0)]
for item in data['items']:
    #item['expanded'] = True
    item['expanded'] = False
data['items'][0]['hover'] = True

screen = curses.initscr()
curses.start_color()
curses.use_default_colors()
curses.init_pair(1, curses.COLOR_RED, -1)
curses.init_pair(2, curses.COLOR_WHITE, -1)
curses.init_pair(3, curses.COLOR_YELLOW, -1)
'''
COLOR = 1
curses.init_pair(1, curses.COLOR_BLUE, -1)
curses.init_pair(2, curses.COLOR_CYAN, -1)
curses.init_pair(3, curses.COLOR_GREEN, -1)
curses.init_pair(4, curses.COLOR_MAGENTA, -1)
curses.init_pair(5, curses.COLOR_RED, -1)
curses.init_pair(6, curses.COLOR_WHITE, -1)
curses.init_pair(7, curses.COLOR_YELLOW, -1)
'''
screen.keypad(1)
curses.curs_set(0)
curses.noecho()

write_x = write_y = edit_x = edit_y = 0

k = 0
while k != ord('q'):
    draw(screen, data)
    #screen.addstr(33, 100, '[+] Text goes here.')
    k = screen.getch()

    (parent, index) = position[-1]
    self = parent['items'][index] if parent['items'] else []

    if k == ord('j'):
        move_down(parent, index, position)
    elif k == ord('k'):
        move_up(parent, index, position)
    elif k == ord('h'):
        move_left(parent, self, position)
    elif k == ord('l'):
        move_right(self, position)
    elif k == ord('\t'):
        flip_expansion(self)
    elif k == ord(' '):
        if parent['items']:
            (top_parent, top_index) = position[0]
            flip_recursively(self, not parent['items'][index]['expanded'])
    elif k == ord('d'):
        if len(position) == 1:
            os.remove(path + self['caption'])
        deleted.append(self)
        delete(parent, index, position)
        if len(position):
            save_category(path, data, position)
    elif k == ord('o') or k == ord('O'):
        below = 1 if parent['items'] and k == ord('o') else 0
        add_sibling(parent, index, below, position)
        save_category(path, data, position)
    elif k == ord('a'):
        if data['items']:
            add_child(parent, index, position)
        save_category(path, data, position)
    elif k == ord('e'):
        old_caption = self['caption']
        edit_caption(self)
        save_category(path, data, position)
        if len(position) == 1 and old_caption != self['caption']:
            os.remove(path + old_caption)
    elif k == ord('s'):
        save_category(path, data, position)
    elif k == ord('\n'):
        flip_marked(self)
        save_category(path, data, position)
    elif k == ord('t'):
        update_time(self)
        save_category(path, data, position)
    elif k == ord('p') or k == ord('P'):
        if deleted != []:
            item = deleted.pop()
            below = 1 if parent['items'] and k == ord('p') else 0
            paste(parent, index, item, below, position)
            save_category(path, data, position)
    elif k == ord('+') and zoom_level < len(position):
        flip_marked(self)
        zoom_level += 1
    elif k == ord('-') and zoom_level > 0:
        zoom_level -= 1
    '''
    elif k ==ord('+'):
        #flip_marked(self)
        zoom.append((data['items'], list(position)))
        data['items'] = [self]
        position = [(data, 0)]
    elif k == '-' and zoom:
        d, p = zoom.pop()
        data['items'] = d
        position = p
    '''

    # When editing top element,  delete and write file again


curses.endwin()

