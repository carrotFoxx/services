#!/usr/bin/env python3
import argparse
import logging
import os
import re
import sys

logger = logging.getLogger()


class VersionForger:
    def __init__(self):
        self._rev = None
        self._suffix = None
        self._major, self._minor, self._patch, self._diff, _ = self._git_describe()
        if self._diff is not None:
            if self._patch == -1:
                self._minor += 1
            self._patch += 1

    @property
    def semver(self):
        """
        :return: a X.Y.Z (Major.Minor.Patch) formatted version according to SEMVER spec
        """
        return '%s.%s.%s' % (self._major, self._minor, self._patch)

    @property
    def short(self):
        """
        :return: a X.Y (Major.Minor) formatted version
        """
        return '%s.%s' % (self._major, self._minor)

    @property
    def major(self):
        return self._major

    @property
    def minor(self):
        return self._minor

    @property
    def patch(self):
        return self._patch

    @property
    def release_kind(self):
        if self._suffix is None:
            self._suffix = self._release_suffix()
        return self._suffix

    @property
    def revision(self):
        """
        :return: a full git revision sha1 hash
        :rtype: str
        """
        if self._rev is None:
            self._rev = self._git_rev()
        return self._rev

    @property
    def release(self):
        """
        :return: a PEP440 compatible release identifier
        :rtype: str
        """
        return '{semver}{kind}{diff}+{rev}'.format(
            semver=self.semver,
            kind=self.release_kind if self._diff else '',
            diff=self._diff or '',
            rev=self.revision[:7]
        )

    _RE_GIT_DESC = re.compile(r'^v?((\d+).(\d+)(.(\d+))?)(-(\d+)-([0-9A-Za-z]+))?$')

    _MASTER_BRANCHES = ('master', 'release')
    _TRUNK_BRANCHES = ('develop', 'development', 'trunk')

    @staticmethod
    def _git_rev():
        """
        :return: git commit hash of current codebase state
        :rtype: str
        """
        rev = os.popen('git rev-parse HEAD').read().strip()  # type: str
        logger.debug('parsed git revision: %s', rev)
        return rev

    @staticmethod
    def _git_branch():
        """
        :return: git current branch name
        :rtype: str
        """
        branch = os.popen('git branch | grep \*').read().strip()  # type: str
        branch = branch.replace('* ', '')
        logger.debug('parsed git branch: %s', branch)
        return branch

    def _git_describe(self):
        git_rev = os.popen('git describe --tags').read().strip()  # type: str
        if git_rev == '':
            git_rev = '0.0.0'
        logger.debug('git describe output:\n%s', git_rev)
        groups = self._RE_GIT_DESC.match(git_rev).groups()
        logger.debug('parsed git describe, matched groups: %s', groups)
        major = int(groups[1])
        minor = int(groups[2])
        patch = int(groups[4]) if groups[3] is not None else -1
        diff = int(groups[6]) if groups[5] is not None else None
        rev = groups[7] or ''

        return major, minor, patch, diff, rev

    def _release_suffix(self):
        git_branch = self._git_branch()
        if git_branch in self._MASTER_BRANCHES:  # preview release
            suffix = 'rc'
        elif git_branch in self._TRUNK_BRANCHES:  # beta release
            suffix = 'b'
        else:  # alpha release
            suffix = 'a'
        logger.debug('determined release suffix: %s', suffix)
        return suffix


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='''
        GitAppVersionFetcher
        uses git info to create a version/release identifier of form: x.y.z[(a|b|rc)N+gitref]
        '''
    )
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('-d', '--dir', type=str, dest='work_dir', help='pick git info from this dir')
    parser.add_argument('-o', '--out', type=str, dest='output', default='version.info',
                        help='where to output version identifier, use `-` for stdout')
    parser.add_argument('-f', '--format', type=str, dest='format', default='release',
                        choices=('semver', 'major', 'short', 'release', 'revision'),
                        help='version format')
    args = parser.parse_args()
    if args.debug:
        logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

    if args.work_dir is not None:
        logger.info('using cwd [%s]', args.work_dir)
        os.chdir(args.work_dir)
    forge = VersionForger()
    v = getattr(forge, args.format)
    if args.output == '-':
        sys.stdout.write(v)
    else:
        logger.info('compiled file [%s] with [%s]', args.output, v)
        with open(args.output, 'w') as fd:
            fd.write(v)
