# -*- coding: utf-8 -*-
'''
File:

Authors:       Jun Lu (lujun@mail.nih.gov)

Created:

Abstract:      A utility for generating .map files where modifying sample/locus ids are necessary.
               It is necessary to modify mapper.py first before to run this scripts

Requires:      Python 2.4

Revision:
'''

__version__ = '0.1'
__copyright__ = 'Copyright (c) 2006 Science Applications International Corporation ("SAIC"). All rights reserved.'

import sys
import csv
from   itertools              import islice,imap,chain,groupby
from   operator               import itemgetter

from   biozilla.utils         import autofile,hyphen
from   biozilla.genoarray     import snp_acgt
from   biozilla.genodata      import  *
from   app_utils              import  mapper,mapper2
import re


def get_ids(filename,nskiprows,nskipcols,iscol=False, filtercol=None,filterval=None):
  '''
  '''
  rows = csv.reader(autofile(filename),dialect='excel-tab')
  rows = islice(rows,nskiprows,None)

  if not iscol:
    row = rows.next()
    return row[nskipcols:]

  else:
    if filterval:
      p = re.compile('^'+filterval)
      if  filterval[0] != '!':
        return [row[nskipcols] for row in rows if p.findall(row[filtercol-1])]
      else:
        p = re.compile('^'+filterval[1:])
        return [row[nskipcols] for row in rows if not p.findall(row[filtercol-1])]
    else:
      return [row[nskipcols] for row in rows]


def map_ids(ids,keepwell=False,sep=None,join='1:'):
  if not len(ids):
    print >> sys.stderr,'\nWARNING: NO identifers being extracted, please check the specifications!\n'
    return

  else:
    print >> sys.stderr,'The total number of identifers:   %s' % len(ids)
    if len(set(ids)) != len(ids):
      print >> sys.stderr,'Warning: Original identifiers are NOT unique'

    orig2new = {}
    tmpset  = set()
    for j in ids:
      if keepwell:
        newid = mapper2(j,sep,join)
      else:
        newid = mapper(j,sep,join)
      #if newid in tmpset:
      #  print >> sys.stderr,'Warning: multiple (orig) to one (new) mapping, original %s, new %s'%(j,newid)
      orig2new[j] = newid
      tmpset.add(newid)

  return orig2new


def output_map(infile,outfile,fromcol=None,tocol=None,cols=None,nskiprows=0,filtercol=None,filterval=None):
  rows = csv.reader(autofile(infile),dialect='excel-tab')
  rows = islice(rows,nskiprows,None)

  out = csv.writer(autofile(outfile, 'w'),dialect='excel-tab')
  #out.writerow(['FROM','TO'])
  for row in rows:
    exclude = False
    if filterval:
      if filterval[0] == '!':
        p = re.compile('^'+filterval[1:])
        exclude = ( p.findall(row[filtercol-1]) )
      else:
        p = re.compile('^'+filterval)
        exclude=  ( not p.findall(row[filtercol-1]) )
      if exclude:
        continue
    if tocol:
      if not row[tocol-1]:
        print >> sys.stderr,'\n---Warning: Empty cell for this row: %s\t%s !!!\n' % (row[fromcol-1],row[tocol-1])
      out.writerow([row[fromcol-1].strip(),row[tocol-1].strip()])
    elif cols:
      out.writerow([row[int(i)-1].strip() for i in cols.split(',')])
    else:
      raise ValueError, 'Error: need to specify either from-to-col or cols!'


def output_ids(filename,orig2new,isreverse=False,gripdata=False):
  out = csv.writer(autofile(filename, 'w'),dialect='excel-tab')
  if gripdata:
    out.writerow(['YOUR_LIST'])
  else:
    out.writerow(['FROM','TO'])

  for old_id,new_id in orig2new.iteritems():
    if gripdata=='old':
      out.writerow([old_id])
    elif gripdata=='new':
      out.writerow([new_id])
    elif isreverse:
      out.writerow([new_id,old_id])
    else:
      out.writerow([old_id,new_id])


def create_sid_map(outfile,sidfile,orig2new):
  '''
  '''
  sb2sid = load_map(sidfile)
  out = csv.writer(autofile(outfile, 'w'),dialect='excel-tab')
  for k,v in orig2new.iteritems():
    if v in sb2sid:
      out.writerow([k,sb2sid.get(v)])


def create_exp_dups_ident(outfile,sampledef,orig2new,phenofile=None):
  '''
  Identifiler_id, PID, CGFID,SID,...
  '''
  if phenofile:
    sid2pid = {}
    rows = csv.reader(autofile(phenofile),dialect='excel-tab')
    h  = rows.next()
    for r in rows:
      sid2pid[r[0]] = [r[1],r[0]] + r[2:] if len(r)>2 else [r[1],r[0]]

    sb2sid  = load_map(sampledef)

    out = csv.writer(autofile(outfile, 'w'),dialect='excel-tab')
    out.writerow(['Long_SB']+[h[1],h[0]] + h[2:])
    for k,v in orig2new.iteritems():
      if v in sb2sid:
        sid =  sb2sid.get(v)
        if sid in sid2pid:
          out.writerow([k] + sid2pid.get(sid,[]))
      else:
        print >> sys.stderr, 'NO corresponding SID# for the sample: %s ' % k
  else:
    sb2sid = {}
    rows = csv.reader(autofile(sampledef),dialect='excel-tab')
    h  = rows.next()
    for r in rows:
      sb2sid[r[0]] = [r[1],r[0]] + r[2:]

    out = csv.writer(autofile(outfile, 'w'),dialect='excel-tab')
    out.writerow(['IID']+[h[1],h[0]] + h[2:])
    for k,v in orig2new.iteritems():
      if v in sb2sid:
        out.writerow([k] + sb2sid.get(v))
      else:
        print >> sys.stderr, 'NO corresponding SID# for the sample: %s ' % k


def create_exp_dups(outfile,dupfile,orig2new):
  '''
  '''
  new2orig = {}
  for orig,new in orig2new.iteritems():
    new2orig.setdefault(new,{})[orig] = None

  rows = csv.reader(autofile(dupfile),dialect='excel-tab')

  out = csv.writer(autofile(outfile, 'w'),dialect='excel-tab')
  for row in rows:
    arow = []
    for a in row:
      n_a = mapper(a)
      if n_a in new2orig:
        arow += new2orig[n_a].keys()
      else:
        arow.append(a)

    if len(arow) > 1:
      out.writerow(arow)


def subset_rows(infile,outfile,filtercol,rowinclude,rowexclude,headerinclude):
  rows = csv.reader(autofile(infile),dialect='excel-tab')
  out  = csv.writer(autofile(outfile, 'w'),dialect='excel-tab')

  if headerinclude:
    out.writerow(rows.next())

  in_list = ex_list = []
  if rowinclude:
    in_list = load_map(rowinclude)
    in_list = [k.lower() for k in in_list]
  elif rowexclude:
    ex_list = load_map(rowexclude)
    ex_list = [k.lower() for k in ex_list]
  else:
    print >> sys.stderr,'Please provide an include, or exclude list file'

  for r in rows:
    is_include = False
    if in_list:
      is_include = ( r[filtercol-1].lower() in in_list )

    if ex_list:
      is_include = ( r[filtercol-1].lower() not in ex_list )

    if is_include:
      out.writerow(r)


def option_parser():
  import optparse

  usage = 'usage: %prog [options] inputfile outputfile'
  parser = optparse.OptionParser(usage=usage, version='%%prog %s' % __version__)

  parser.add_option('-f', '--fromcol', dest='fromcol', metavar='N', type='int', default=None,
                    help='Specify the column number containing source identifiers (col starts with 1)')
  parser.add_option('-t', '--tocol', dest='tocol', metavar='N', type='int', default=None,
                    help='Specify the column number containing target identifiers (col starts with 1)')

  parser.add_option('-c', '--cols', dest='cols', metavar='STRING', default=None,
                    help='Specify which set of columns (one or more) needs to be output (separated by comma)')

  parser.add_option('-s', '--nskiprows', dest='nskiprows', metavar='N', type='int', default=0,
                    help='Specify the number of rows skipped (default=0), used to find the row (col) of identifiers')
  parser.add_option('-S', '--nskipcols', dest='nskipcols', metavar='N', type='int', default=1,
                    help='Specifiy the number of columns skipped (default=1), used to find the row (col) of identifiers')
  parser.add_option('-v', '--iscolumn', dest='iscolumn', action='store_true', default=False,
                    help='Specify whether identifiers are in a column (default=False)')

  parser.add_option('-e', '--gripdata', dest='gripdata', metavar='STRING', default=None,
                    help='Specify which set of identifiers (one and only one) need to be output (choose "old","new")')

  parser.add_option('-r', '--isreverse', dest='isreverse', action='store_true', default=False,
                    help='Specifying the direction of identifier mapping in output(default is from old (left) to new (right))')

  parser.add_option(     '--dupfile', dest='dupfile', metavar='FILE', default=None,
                    help='specifying duplicates file (optional)')

  parser.add_option(     '--filtercol', dest='filtercol', metavar='N', type='int',default=None,
                    help='Specify the column used to filter the ids')
  parser.add_option(     '--filterval', dest='filterval', metavar='STRING', default=None,
                    help='Specify the matched string where ids would be kept (e.g. Validated, !Failed)')

  parser.add_option(     '--sidfile', dest='sidfile', metavar='FILE', default=None,
                    help='specifying short SB # to SID file (usually _Sample.txt, optional)')

  parser.add_option('-w', '--keepwell', dest='keepwell', action='store_true', default=False,
                    help='keep the well# in the new id names')

  parser.add_option(     '--sampledef', dest='sampledef', metavar='FILE', default=None,
                    help='specifying sample.def file used to create a new sample.def')

  parser.add_option(     '--phenofile', dest='phenofile', metavar='FILE', default=None,
                    help='specifying investigator phenotype file')

  parser.add_option(     '--rowinclude', dest='rowinclude', metavar='FILE', default=None,
                    help='specifying a file with a list of includes')

  parser.add_option(     '--rowexclude', dest='rowexclude', metavar='FILE', default=None,
                    help='specifying a file with a list of excludes')

  parser.add_option('-T', '--headerinclude', dest='headerinclude', action='store_true', default=False,
                    help='keep the header when selecting rows')

  parser.add_option(     '--splitpattern', dest='splitpattern', metavar='string', default=None,
                    help='patterns for mapping old ids to new ids,e.g. /\s/')
  parser.add_option(     '--joinstr', dest='joinstr', metavar='string', default='1:',
                    help='specifying the rejoining elements and the separator, default=1: (i.e. first element)')

  #parser.add_option(     '--dupformat', dest='dupformat', metavar='STRING', default='duplicates',
  #                  help='Specify format of expected duplicates file (choose "duplicates","pid")')
  #parser.add_option(     '--dupskip', dest='dupskip', metavar='N', type='int', default=0,
  #                  help='specifying number of skipped rows in the duplicates file (optional)')

  return parser


def main():
  parser = option_parser()
  options,args = parser.parse_args()

  if len(args) != 2:
    parser.print_help()
    return

  #source and target ids exist
  if options.tocol:
    if not options.fromcol:
      print >> sys.stderr,'Stopped: need to specify -f option (fromcols)'
      return

  # select cols
  if options.cols or options.tocol:
    output_map(args[0],args[1],options.fromcol,options.tocol,options.cols, \
               options.nskiprows,options.filtercol,options.filterval)
  # select rows
  elif options.rowinclude or options.rowexclude:
    subset_rows(args[0],args[1],options.filtercol,options.rowinclude,options.rowexclude,options.headerinclude)
  # map ids
  else:
    ids = get_ids(args[0],options.nskiprows,options.nskipcols, \
                  options.iscolumn,options.filtercol, options.filterval)
    orig2new = map_ids(ids,options.keepwell,options.splitpattern, options.joinstr)
    if options.dupfile:
      create_exp_dups(args[1],options.dupfile,orig2new)
    elif options.sidfile:
      create_sid_map(args[1],options.sidfile,orig2new)
    elif options.sampledef:
      create_exp_dups_ident(args[1],options.sampledef,orig2new,options.phenofile)
    else:
      output_ids(args[1],orig2new,options.isreverse,options.gripdata)


if __name__ == '__main__':
  main()
