#!/usr/bin/env python3

import matplotlib.pyplot as plt
import glob
import argparse
import ujson as json
import numpy as np
import statsmodels.api as sm # recommended import according to the docs
#http://stackoverflow.com/questions/23343484/python-3-statsmodels
import matplotlib
matplotlib.rcParams['text.usetex'] = True
from mpl_toolkits.axes_grid1.inset_locator import zoomed_inset_axes
from mpl_toolkits.axes_grid1.inset_locator import mark_inset

MIN_STEP = 1
MAX_STEP = 10
TYPES    = [
    'rae2cor',
    'rae2plr',
    'rae2rar_other',
    'rae2rar_eye'
]

# http://stackoverflow.com/questions/7799156/can-i-cycle-through-line-styles-in-matplotlib
colors      = ('k', 'g', 'b', 'r')
linestyles  = ('-','--','-.',':')
styles      = ['{}{}'.format(color,linestyles[i]) for i,color in enumerate(colors)]
style_index = 0
fontsize    = 20

parser = argparse.ArgumentParser(description="plot % latency diffs cdf")
parser.add_argument('-i', '--input', dest='input_dir', type=str, help='directory with all valid_ping_median jsons', required=True)
parser.add_argument('-u', '--use_median', dest='use_median', type=bool, help='use median instead of min', default=False)
parser.add_argument('--min', dest='min', type=int, help="minimum value on x-axis", default=0)
parser.add_argument('--max', dest='max', type=int, help="maximum value on x-axis", default=None)
parser.add_argument('-o', '--output', dest='output_figure_file', type=str, help='png/ps figure file for output', required=True)
args = parser.parse_args()

# initialize results
results = {}
for type in TYPES:
    results[type] = []

# gather results
for msm_res_json in glob.iglob('{}/msm_*_valid_ping_medians.json'.format(args.input_dir)):
    with open(msm_res_json, 'r') as f:
        this_res = json.load(f)

    for pair in this_res:
        for type in TYPES:
            if len(this_res[pair][type].values()) > 0:
                rae_node        = list(this_res[pair]['rae2rae'].keys())[0]
                rae2rae_median  = this_res[pair]['rae2rae'][rae_node]['median']
                if not args.use_median:
                    rel_median = min([v['median'] for v in this_res[pair][type].values()])
                else:
                     rel_median = np.median([v['median'] for v in this_res[pair][type].values()])
                #diff            = (rae2rae_median - rel_median)/(1.0*rae2rae_median)
                #perc_diff       = diff * 100.0
                diff = (rae2rae_median - rel_median)
                results[type].append(diff)

# set cdfs
ecdfs = {}
for type in TYPES:
    ecdfs[type] = sm.distributions.ECDF(results[type])

# set x axes
x     = {}
x_min = min([min(results[type]) for type in TYPES])
x_max = max([max(results[type]) for type in TYPES])
if args.min is not None:
    x_min = args.min
if args.max is not None:
    x_max = args.max
for type in TYPES:
    x[type] = np.linspace(x_min, x_max, 1000)

# set y axes
y = {}
for type in TYPES:
    y[type] = ecdfs[type](x[type])

fig, ax = plt.subplots()
plt.subplots_adjust(bottom=0.15)
plt.subplots_adjust(top=0.9)
for type in TYPES:
    ax.plot(x[type], y[type], styles[style_index], label='{}'.format(type).replace('rae2', '').replace('_', '\_').upper())
    style_index = (style_index + 1) % len(styles)

# set xticks
xticks = []
cur_x = int(x_min)
xticks.append(cur_x)
while cur_x < x_max:
    xticks.append(cur_x)
    cur_x += 50 # x-step
xticks.append(int(x_max))
plt.xticks(xticks, fontsize = fontsize)
plt.xlim(x_min, x_max)

# set yticks
yticks = []
cur_y = 0.2
yticks.append(cur_y)
while cur_y < 1.0:
    yticks.append(cur_y)
    cur_y += 0.1 # y-step
yticks.append(1.0)
plt.yticks(yticks, fontsize = fontsize)

# set legend
#legend = ax.legend(loc='lower right', fontsize=fontsize, frameon=True, edgecolor='k')
legend = ax.legend(bbox_to_anchor=(0., 1.02, 1., 1), loc=3, fontsize=16,
           ncol=4, mode="expand", borderaxespad=0., handlelength=1.0, handletextpad=0.5)

# set xlabel
plt.xlabel("Latency (ms) improvement vs. direct paths", fontsize=fontsize)

# set title
#plt.title("CDF of total positive % overlay latency improvement", fontsize=fontsize)

# activate grid
ax.grid(True, which='both')
ax.xaxis.grid(linestyle=':')
ax.yaxis.grid(linestyle=':')

# inset figure

# zoom in
#http://matplotlib.org/1.3.1/mpl_toolkits/axes_grid/users/overview.html
#http://akuederle.com/matplotlib-zoomed-up-inset

#'best'         : 0, (only implemented for axes legends)
#'upper right'  : 1,
#'upper left'   : 2,
#'lower left'   : 3,
#'lower right'  : 4,
#'right'        : 5,
#'center left'  : 6,
#'center right' : 7,
#'lower center' : 8,
#'upper center' : 9,
#'center'       : 10,

axinset = zoomed_inset_axes(ax, 2.0, loc=7) # zoom = 1.0, location: center right
style_index = 0
for type in TYPES:
    axinset.plot(x[type], y[type], styles[style_index])
    style_index = (style_index + 1) % len(styles)

cur_x = 0
while cur_x < 20:
    xticks.append(cur_x)
    cur_x += 5 # x-step
xticks.append(20)
plt.xticks(xticks)

# sub region of the original image
x1, x2, y1, y2 = 0, 20, 0.4, 0.7
axinset.set_xlim(x1, x2)
axinset.set_ylim(y1,y2)

# activate grid
axinset.grid(True, which='both')
axinset.xaxis.grid(linestyle=':')
axinset.yaxis.grid(linestyle=':')

#plt.xticks(visible=False)
#plt.yticks(visible=False)

# draw a bbox of the region of the inset axes in the parent axes and
# connecting lines between the bbox and the inset axes area
mark_inset(ax, axinset, loc1=2, loc2=3, fc="None", ec="0.5")

# misc
#plt.tight_layout()
#plt.show()
plt.savefig(args.output_figure_file)
plt.close()
