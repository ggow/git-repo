#
# Copyright (C) 2012 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import string
from git_command import GitCommand

from command import PagedCommand
from color import Coloring
from error import NoSuchProjectError

class _Coloring(Coloring):
  def __init__(self, config):
    Coloring.__init__(self, config, "repoinfo")

class Info(PagedCommand):
  common = True
  helpSummary = "Get info on the manifest branch, current branch or unmerged branches"
  helpUsage = "%prog [-a] [-o [-b]] [<project>...]"

  def _Options(self, p, show_smart=True):
    p.add_option('-a', '--all',
                 dest='all', action='store_true',
                 help="show full info")
    p.add_option('-o', '--overview',
                 dest='overview', action='store_true',
                 help='show overview of all commits')
    p.add_option('-b', '--current-branch',
                 dest="current_branch", action="store_true",
                 help="consider only checked out branches")

  def Execute(self, opt, args):
    self.out = _Coloring(self.manifest.globalConfig)
    self.heading = self.out.printer('heading', attr = 'bold')
    self.headtext = self.out.printer('headtext', fg = 'yellow')
    self.redtext = self.out.printer('redtext', fg = 'red')
    self.sha = self.out.printer("sha", fg = 'yellow')
    self.text = self.out.printer('text')
    self.dimtext = self.out.printer('dimtext', attr = 'dim')

    self.opt = opt

    mergeBranch = self.manifest.manifestProject.config.GetBranch("default").merge

    self.heading("Manifest branch: ")
    self.headtext(self.manifest.default.revisionExpr)
    self.out.nl()
    self.heading("Manifest merge branch: ")
    self.headtext(mergeBranch)
    self.out.nl()

    if not opt.overview:
      self.printLocalInfo(args)
    else:
      self.printOverview(args)

  def printLocalInfo(self, args):
    if len(args) > 0:
      projects = args
    else:
      projects = ["."]

    try:
      projs = self.GetProjects(projects)
    except NoSuchProjectError:
      return

    for p in projs:
      self.heading("Project: ")
      self.headtext(p.name)
      self.out.nl()

      self.heading("Mount path: ")
      self.headtext(p.worktree)
      self.out.nl()

      self.heading("Current revision: ")
      self.headtext(p.revisionExpr)
      self.out.nl()

      localBranches = self.localBranches(p)
      self.heading("Local Branches: ")
      self.redtext(str(len(localBranches)))
      self.text(" [")
      self.text(string.join(localBranches, ", "))
      self.text("]")
      self.out.nl()

      if self.opt.all:
        self.findRemoteLocalDiff(p)

  def localBranches(self, project):
    #get all the local branches
    gc = GitCommand(project, ["branch"], capture_stdout=True, capture_stderr=True)
    gc.Wait()
    localBranches = []
    for line in gc.stdout.splitlines():
      localBranches.append(line.replace('*','').strip())

    return localBranches

  def findRemoteLocalDiff(self, project):
    #Fetch all the latest commits
    GitCommand(project, ["fetch", "--all"], capture_stdout=True, capture_stderr=True).Wait()

    #Find branches
    gc = GitCommand(project, ["branch", "-r"], capture_stdout=True, capture_stderr=True)
    gc.Wait()
    isOnBranch = False
    for line in gc.stdout.splitlines():
      if "->" in line:
        isOnBranch = True
        break

    #Index the remote commits
    if isOnBranch:
      logTarget = "origin/" + project.revisionExpr
    else:
      logTarget = project.revisionExpr

    #index the local commits
    gc = GitCommand(project, ["log", "--pretty=oneline", logTarget + ".."], capture_stdout=True, capture_stderr=True)
    gc.Wait()
    localCommits = []
    for line in gc.stdout.splitlines():
      localCommits.append(line)

    gc = GitCommand(project, ["log", "--pretty=oneline", ".." + logTarget], capture_stdout=True, capture_stderr=True)
    gc.Wait()
    originCommits = []
    for line in gc.stdout.splitlines():
      originCommits.append(line)

    self.heading("Local Commits: ")
    self.redtext(str(len(localCommits)))
    self.dimtext(" (on current branch)")
    self.out.nl()

    for c in localCommits:
      split = c.split()
      self.sha(split[0] + " ")
      self.text(string.join(split[1:]))
      self.out.nl()

    self.text("----------------------------")
    self.out.nl()

    self.heading("Remote Commits: ")
    self.redtext(str(len(originCommits)))
    self.out.nl()

    for c in originCommits:
      split = c.split()
      self.sha(split[0] + " ")
      self.text(string.join(split[1:]))
      self.out.nl()

  def printOverview(self, args):
    all = []
    for project in self.GetProjects(args):
      br = [project.GetUploadableBranch(x)
            for x in project.GetBranches().keys()]
      br = [x for x in br if x]
      if self.opt.current_branch:
        br = [x for x in br if x.name == project.CurrentBranch]
      all.extend(br)

    if not all:
      return

    self.out.nl()
    self.heading('Projects Overview')
    project = None

    for branch in all:
      if project != branch.project:
        project = branch.project
        self.out.nl()
        self.headtext(project.relpath)
        self.out.nl()

      commits = branch.commits
      date = branch.date
      self.text('%s %-33s (%2d commit%s, %s)' % (
        branch.name == project.CurrentBranch and '*' or ' ',
        branch.name,
        len(commits),
        len(commits) != 1 and 's' or ' ',
        date))
      self.out.nl()

      for commit in commits:
        split = commit.split()
        self.text('{0:38}{1} '.format('','-'))
        self.sha(split[0] + " ")
        self.text(string.join(split[1:]))
        self.out.nl()
