import config
from wrappers import standard_wrap, tlp_wrap
from selector import Selector
from html import *
from utils import getformslot
import re, datetime

s = Selector(wrap=standard_wrap)
application = tlp_wrap(s)
s.parser.default_pattern='segment'

import wrappers

def style(thing):
  return [str(as_html(thing))]
#  return [unicode(as_html(thing)).decode(config.unicode_encoding)]

wrappers.style = style

def slashify(req):
  return req.redirect('%s/' % req.environ.get('SCRIPT_NAME'))

def init():
  s.add('', GET=slashify)
  s.add('/', GET=start)
  s.add('/view/{page}', GET=view)
  s.add('/view/{page}/{revision}', GET=view)
  s.add('/edit/{page}', GET=edit)
  s.add('/post/{page}', POST=post)
  s.add('/static/{file}', GET=static)
  pass

template = open('uWiki.template').read()
spath = '/static'
content_type_header = 'text/html; charset=' + config.unicode_encoding
helptext = open('markdown-ref.txt').read()  # For inclusion on editing page

class rcstore(object):

  HTML = 'html'
  MARKDOWN = 'mrk'
  METADATA = 'mtd'
  REVISION = 'rev'
  
  def __init__(self, db = {}):
    self.db = db
    pass

  def latest_revision(self, name):
    return int(self.db.get('%s.%s' % (name, rcstore.REVISION), 0))

  def get(self, name, type, rev=None):
    rev = rev or self.latest_revision(name)
    return self.db.get('%s~%s.%s' % (name, rev, type))
  
  def store(self, name, markdown, html, metadata):
    rev = self.latest_revision(name)
    if rev:
      old_markdown = self.get(name, rcstore.MARKDOWN)
      if markdown == old_markdown: return # Don't store content if unchanged
      pass
    rev = rev + 1
    self.db['%s~%s.%s' % (name, rev, rcstore.MARKDOWN)] = markdown
    self.db['%s~%s.%s' % (name, rev, rcstore.HTML)] = html
    self.db['%s~%s.%s' % (name, rev, rcstore.METADATA)] = metadata
    self.db['%s.%s' % (name, rcstore.REVISION)] = str(rev)
    pass

  pass

content = rcstore({})

def static(req):
  return HTMLString(open(req.environ['selector.vars']['file']).read())

def start(req):
  req.redirect('/view/Start')

def view(req):
  req.res.headers['Content-type'] = content_type_header
  name = req.environ['selector.vars']['page']
  rev = req.environ['selector.vars'].get('revision')
  markdown = content.get(name, rcstore.MARKDOWN, rev)
  html = content.get(name, rcstore.HTML, rev)
  
  if rev:
    # View a particular revision
    if not markdown: return ['%s revision %s not found' % (name, rev)]
    return ['%s revision %s ' % (name, rev),
            link('(back)', '/view/%s' % name), HR, HTMLString(html)]

  # View the latest revision, with options to edit or view previous revs
  if markdown:
    l = [name, ' | ', link('EDIT', '/edit/%s' % name)]
    revs = content.latest_revision(name)
    if revs>1:
      l.append(' | Previous versions: ')
      l.extend([link(str(i), '/view/%s/%s' % (name, i))
                for i in range(1, revs)])
      pass
    l.append(HR)
    l.append(HTMLString(html))
    return HTMLItems(*l)
  else:
    # Page not found
    l = [name, ' not found. ', link('Create it', '/edit/%s' % name)]
    r = req.environ.get('HTTP_REFERER') or req.environ.get('HTTP_REFERRER')
    if r: l.append(HTMLItems(' or ', link('cancel', r)))
    return HTMLItems(*l)
  pass

def edit(req):
  req.res.headers['Content-type']='text/html'
  name = req.environ['selector.vars']['page']
  base_version = content.latest_revision(name)
  markdown = content.get(name, rcstore.MARKDOWN) or '# %s\n\nNew page' % name
  d = { 'name' : name, 'md_content' : markdown, 'spath' : spath,
        'base_version' : base_version, 'helptext' : helptext, 'msg' : name }
  return HTMLString(template % d)

def post(req):
  name = req.environ['selector.vars']['page']
  latest_version = content.latest_revision(name)
  base_version = int(getformslot('base_version'))
  if latest_version != base_version:
    return resolve(name, base_version, latest_version)
  content.store(name, getformslot('content'), getformslot('html'),
                str({'timestamp' : datetime.datetime.now()}))
  return req.redirect('/view/%s' % name)

import merge3, StringIO

def lines(s): return StringIO.StringIO(s).readlines()

merge_msg = '''Someone else has modified this page since you started editing
it. Your changes have been merged with theirs.  Please check that the results
of the merge are satisfactory and re-save the page.'''

conflict_msg = '''Someone else has modified this page since you started editing
it.  Trying to merge your changes has resulted in conflicts that cannot be
automatically resolved.  Please resolve these conflicts manually and re-save
the page.'''

def resolve(name, base_version, latest_version):
  new = getformslot('content')
  base = content.get(name, rcstore.MARKDOWN, base_version) or ''
  latest = content.get(name, rcstore.MARKDOWN, latest_version) or ''
  m = merge3.Merge3(lines(base), lines(new), lines(latest))
  mg = list(m.merge_groups())
  conflicts = 0
  for g in mg:
    if g[0]=='conflict': conflicts+=1
    pass
  merged = ''.join(m.merge_lines(
    start_marker='\n!!!--Conflict--!!!\n!--Your version--',
    mid_marker='\n!--Other version--',
    end_marker='\n!--End conflict--\n'))
  d = { 'name' : name, 'md_content' : merged, 'spath' : spath,
        'base_version' : latest_version, 'helptext' : helptext,
        'msg' : conflict_msg if conflicts else merge_msg }
  return HTMLString(template % d)
