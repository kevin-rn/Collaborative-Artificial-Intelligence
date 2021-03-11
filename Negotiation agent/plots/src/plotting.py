'''
Created on 25 feb. 2021

@author: hugoj
'''
import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt
from numpy import double
import numpy as np
import csv


util = np.loadtxt(open("utilities.txt", "rb"), delimiter=",")
# print(util[0])
utildf = pd.DataFrame(data=util, columns=['other', 'me'])
# print(utildf[0])
#
utilnames = pd.read_csv("utilitiesPartyIds.txt", header=None)
# print(utilnames)
utildf['party'] = utilnames
# utilddf = pd.DataFrame({"party": utilnames})
# df = pd.DataFrame(df, columns = ["X", "Y"])
# print(df)

# print([utildf, utilnames])

groups = utildf.groupby("party", sort=False)
# groupnames = list(groups.groups)
groupnames = [name for name,unused_df in groups]
if groupnames[0] != "Group19Party_1": groupnames.reverse()
print(groupnames.reverse())
colors = ['#ff7f0e', '#1f77b4']
for i, (name, group) in enumerate(groups):
    plt.plot(group["other"], group["me"], marker="o", linestyle="-", label=name, color=colors[i])

accept = (utildf.iloc[[-1]][['other', 'me']])
plt.plot(accept['other'], accept['me'],  marker="D", color='red', markersize=10)
# pd.plotting.scatter_matrix(df, alpha=0.2)
# # plt.show()
pom = np.loadtxt(open("pom.txt", "rb"), delimiter=",")
pomdf = pd.DataFrame(data=pom)
# print(pomdf)

# util = np.loadtxt(open("utilities.txt", "rb"), delimiter=",")
# # utildf = pd.DataFrame(data=util)
# print(util)
# with open('pom.txt') as csvfile:
    # data = [(double(x), double(y)) for x, y in csv.reader(csvfile, delimiter= ',')]
# print(df[0])
if(pomdf.shape != (2,1)):
    plt.plot(pomdf[0], pomdf[1], '-', color='#2ca02c')
else :
    plt.plot(pomdf[0][0], pomdf[0][1],marker=".", markersize=10, color='#2ca02c')
# plt.plot(utildf[0], utildf[1])
# fig, ax = plt.subplots()
# colors = {'cai_group19_Group19Party_1':'red','geniusweb_exampleparties_conceder_Conceder_2':'green',}
# plt.plot(utildf[0], utildf[1])

plt.ylim(0,1)
plt.xlim(0,1)
plt.xlabel(groupnames[0] + " utility")
plt.ylabel(groupnames[1] + " utility")
plt.grid(b=True, which='major', color='#666666', linestyle='-')
plt.minorticks_on()
plt.grid(b=True, which='minor', color='#999999', linestyle='-', alpha=0.2)
plt.legend()
plt.subplots_adjust(left=0.1, bottom=0.1, right=0.9, top=0.9)
plt.show()