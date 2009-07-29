# -*- coding: utf-8 -*-

__gluindex__  = True
__program__   = 'TagZilla surrogates'
__authors__   = ['Kevin Jacobs (jacobs@bioinformed.com)']
__abstract__  = 'Find LD surrogate for SNPs'
__copyright__ = 'Copyright (c) 2007-2009, BioInformed LLC and the U.S. Department of Health & Human Services. Funded by NCI under Contract N01-CO-12400.'
__license__   = 'See GLU license for terms by running: glu license'
__revision__  = '$Id$'


import sys
import optparse

from   glu.lib.fileutils       import list_reader, table_writer
from   glu.lib.genolib         import geno_options

from   glu.modules.ld.tagzilla import TagZillaOptionParser, check_option01, epsilon, sfloat, \
                                      build_design_score, generate_ldpairs


def option_parser():
  usage = 'usage: %prog [options] genotypes...'
  parser = TagZillaOptionParser(usage=usage)

  inputgroup = optparse.OptionGroup(parser, 'Input options')

  geno_options(inputgroup,input=True,filter=True)

  inputgroup.add_option('-e', '--excludetag', dest='exclude', metavar='FILE', default='',
                          help='File containing loci that are excluded from being a tag')
  inputgroup.add_option('-s', '--subset', dest='subset', metavar='FILE', default='',
                          help='File containing loci that define the subset to be analyzed of the loci that are read')
  inputgroup.add_option('-R', '--range', dest='range', metavar='S-E,...', default='',
                          help='Ranges of genomic locations to analyze, specified as a comma seperated list of start and '
                               'end coordinates "S-E".  If either S or E is not specified, then the ranges are assumed '
                               'to be open.  The end coordinate is exclusive and not included in the range.')
  inputgroup.add_option('-D', '--designscores', dest='designscores', metavar='FILE', type='str', action='append',
                          help='Read in design scores or other weights to use as criteria to choose the optimal tag for each bin')
  inputgroup.add_option('--designdefault', dest='designdefault', metavar='N', type='float', default=0,
                          help='Default design score for any locus not found in a design file')
  inputgroup.add_option('-L', '--limit', dest='limit', metavar='N', type='int', default=0,
                          help='Limit the number of loci considered to N for testing purposes (default=0 for unlimited)')

  outputgroup = optparse.OptionGroup(parser, 'Output options')

  outputgroup.add_option('-o', '--output', dest='output', metavar='FILE', default='-',
                          help="Output tabular LD information for bins to FILE ('-' for standard out)")

  genoldgroup = optparse.OptionGroup(parser, 'Genotype and LD estimation options')

  genoldgroup.add_option('-a', '--minmaf', dest='maf', metavar='FREQ', type='float', default=0.05,
                          action='callback', callback=check_option01,
                          help='Minimum minor allele frequency (MAF) (default=0.05)')
  genoldgroup.add_option('-c', '--mincompletion', dest='mincompletion', metavar='N', default=0, type='int',
                          help='Drop loci with less than N valid genotypes. Default=0')
  genoldgroup.add_option(      '--mincompletionrate', dest='mincompletionrate', metavar='N', default=0, type='float',
                          action='callback', callback=check_option01,
                          help='Drop loci with completion rate less than N (0-1). Default=0')
  genoldgroup.add_option('-m', '--maxdist', dest='maxdist', metavar='D', type='int', default=200,
                          help='Maximum inter-marker distance in kb for LD comparison (default=200)')
  genoldgroup.add_option('-P', '--hwp', dest='hwp', metavar='p', default=None, type='float',
                          action='callback', callback=check_option01,
                          help='Filter out loci that fail to meet a minimum signficance level (pvalue) for a '
                               'test Hardy-Weignberg proportion (no default)')

  bingroup = optparse.OptionGroup(parser, 'LD threshold options')

  bingroup.add_option('-d', '--dthreshold', dest='d', metavar='DPRIME', type='float', default=0.,
                          action='callback', callback=check_option01,
                          help='Minimum d-prime threshold to output (default=0)')
  bingroup.add_option('-r', '--rthreshold', dest='r', metavar='N', type='float', default=0.95,
                          action='callback', callback=check_option01,
                          help='Minimum r-squared threshold to output (default=0.95)')

  parser.add_option_group(inputgroup)
  parser.add_option_group(outputgroup)
  parser.add_option_group(genoldgroup)
  parser.add_option_group(bingroup)

  return parser


def main():
  parser = option_parser()
  options,args = parser.parse_args()

  if not args:
    parser.print_help(sys.stderr)
    sys.exit(2)

  subset  = set()
  exclude = set()

  if options.subset:
    subset = set(list_reader(options.subset))

  if options.exclude:
    exclude = set(list_reader(options.exclude))

  if options.designscores:
    designscores = build_design_score(options.designscores)
    exclude.update(lname for lname,d in designscores.iteritems() if d <= epsilon)

  if options.subset is not None:
    subset.update(exclude)

  direct   = subset - exclude
  subex    = subset | exclude
  indirect = subset & exclude
  locusmap = {}
  seen     = set()

  options.multipopulation = None
  # ldsubset=indirect
  ldpairs = generate_ldpairs(args, locusmap, set(), None, indirect, options)

  missing = '',0
  best_surrogate = {}
  for pairs in ldpairs:
    seen.update(locusmap)
    for lname1,lname2,r2,dprime in pairs:
      if lname1==lname2:
        continue
      elif lname1 in indirect and lname2 not in subex:
        best_locus,best_r2 = best_surrogate.get(lname1,missing)
        if r2 > best_r2:
          best_surrogate[lname1] = lname2,r2
      elif lname2 in indirect and lname1 not in subex:
        best_locus,best_r2 = best_surrogate.get(lname2,missing)
        if r2 > best_r2:
          best_surrogate[lname2] = lname1,r2

  outfile = table_writer(options.output, hyphen=sys.stdout)
  outfile.writerow(['LNAME','SURROGATE','RSQUARED','REASON'])

  one    = sfloat(1)
  reason = 'DIRECT'
  for lname in direct:
    outfile.writerow([lname,lname,one,reason])

  reason = 'INDIRECT'
  for lname,(surrogate,r2) in best_surrogate.iteritems():
    outfile.writerow([lname,surrogate,sfloat(r2),reason])

  reason_nos = 'NO SURROGATE'
  reason_nod = 'NO DATA'

  for lname in subset:
    if lname not in best_surrogate:
      if lname in seen:
        outfile.writerow([lname,'','',reason_nos])
      else:
        outfile.writerow([lname,'','',reason_nod])


if __name__ == '__main__':
  main()