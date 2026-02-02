#!/usr/bin/ksh

#!/usr/bin/zsh -f # zsh with NO dotfiles

# vim:nonumber:nowrap:nobackup:shiftwidth=3

# vim:nonumber:nowrap:nobackup:shiftwidth=3

# BEGIN SVN INFO ################################################################
#
# Purpose:
#
# http://svnbook.red-bean.com/en/1.5/svn.advanced.props.file-portability.html#svn.advanced.props.special.eol-style
# http://svnbook.red-bean.com/en/1.5/svn.advanced.props.special.ignore.html
# http://svnbook.red-bean.com/en/1.5/svn.advanced.props.special.keywords.html
# svn propset svn:keywords "LastChangedDate LastChangedRevision LastChangedBy HeadURL Id"  ...
# LastChangedDate = Date, LastChangedRevision = Revision = Rev, LastChangedBy = Author, HeadURL = URL, Id
#
# svn propset svn:executable ON ...
#
# $URL$
# $Id$
# $Date$
# $Revision$
# $Author$
# @(#) $HeadURL$ $Id$
#
# END SVN INFO ##################################################################

##########################
## Start of selflogging ##
##########################

mex=${0##*/}  # Basename, or drop /path/to/file
me=${mex%%.*} # Drop .ext.a.b
mep=${0%/*}   # Dirname, or only /path/to
mep=$(cd ${mep} ; pwd) # Absolute path
mef="${mep}/${mex}" # Full path and full filename to $0
meb=${mep%/*} # basedir, if mep is .../bin/
# see also further down for host, id, etc

script_name=${0##*/}                               # Basename, or drop /path/to/file
script=${script_name%%.*}                          # Drop .ext.a.b
script_path=${0%/*}                                # Dirname, or only /path/to
script_path=$(cd ${script_path} ; pwd)             # Absolute path
script_path_name="${script_path}/${script_name}"   # Full path and full filename to $0
script_basedir=${script_path%/*}                   # basedir, if mep is .../bin/


host=$(/usr/bin/uname -n)
uname=${host}
os=$(/usr/bin/uname -s)
osver=$(/usr/bin/uname -rs)
arch=$(/usr/bin/uname -p)                          # sparc/i386
global=$( /usr/bin/cat -s /progs/global.txt )
global=${global:-TBD}
id=$(/usr/xpg4/bin/id -u)
usr=$(/usr/xpg4/bin/id -un)
ymd=$(/usr/bin/date +'%Y/%m/%d')


function logg {
   tstamp=$(date +'%Y%m%d-%H:%M:%S')
   print "[${tstamp} ${script}] $@"
   logger -p daemon.notice -t ${script} "$@"
}

if [[ -z ${ZZLOG} ]] ; then
   # TODO: Configuration:
   readonly logbase=/home/jn00956/log
   readonly COMPRESSLOGS=0
   readonly TSTAMPLOGS=0
   readonly MAXLOGS=40
   readonly LOCK=1

   if [[ ${TSTAMPLOGS} -eq 1 ]] ; then
      # With tstamp log:
      tstamp=`date +'%Y%m%d-%H:%M'`
      ZZLOG=${logbase}/${me}.${tstamp}.log
      # TODO: Cleanup $logbase so that there is only $maxlogs there...
      # ls -t ${logbase} | sed -n "${MAXLOGS},\$p" | xargs rm
   else
      # With $MAXLOGS logs
      ZZLOG=${logbase}/${me}

      let n=${MAXLOGS}-1
      let m=${MAXLOGS}
      if [[ ${COMPRESSLOGS} -eq 1 ]] ; then
         bz=".bz2"
      fi
      while [[ ${n} -ge 0 ]] ; do
         if [[ -e ${ZZLOG}.${n}.log ]] ; then
            #print mv ${ZZLOG}.${n}.log ${ZZLOG}.${m}.log
            mv ${ZZLOG}.${n}.log${bz} ${ZZLOG}.${m}.log${bz}
         fi
         let n=n-1
         let m=m-1
      done
      if [[ -e ${ZZLOG}.log ]] ; then
         #print mv ${ZZLOG}.log ${ZZLOG}.${m}.log
         mv ${ZZLOG}.log ${ZZLOG}.${m}.log
         if [[ ${COMPRESSLOGS} -eq 1 ]] ; then
            bzip2 -9 ${ZZLOG}.${m}.log
         fi
      fi
   fi

   readonly ZZLOG=${logbase}/${me}.log
   export ZZLOG
   tty -s
   if [ $? -eq 0 ] ; then
      print "At tty, doing tee"
      logg "Restarting ${me} (${mef} ${0} ${*}) with logging to ${ZZLOG}" | tee ${ZZLOG}
      $0 $* 2>&1 | tee -a ${ZZLOG}
      logg "Ending ${mef}" | tee -a ${ZZLOG}
   else
      #logg "Starting ${mef}" > ${ZZLOG}
      logg "Restarting ${me} (${mef} ${0} ${*}) with logging to ${ZZLOG}" > ${ZZLOG}
      $0 $* 2>&1 >> ${ZZLOG}
      logg "Ending ${mef}" >> ${ZZLOG}
   fi
   if [[ ${COMPRESSLOGS} -eq 1 ]] ; then
      bzip2 -9 ${ZZLOG} # Compress this log...
   fi
   exit # Do not run rest
fi

##########################
## Start of real script ##
##########################

#zsh:
#setopt ksharrays shwordsplit

#set -e # If a command has a non-zero exit status, execute the  ERR  trap,  if  set, and exit. This mode is disabled while reading profiles.
#set -u # Treat unset parameters as an error when  substituting.
#set -o errexit # If a command has a non-zero exit status, execute the  ERR  trap,  if  set, and exit.
#Set -o nounset # Treat unset parameters as an error when  substituting.



start_time=$SECONDS

host=$(/usr/bin/uname -n)
uname=${host}
os=$(/usr/bin/uname -s)
osver=$(/usr/bin/uname -rs)
id=$(/usr/xpg4/bin/id -u)
usr=$(/usr/xpg4/bin/id -un)
ymd=$(/usr/bin/date +'%Y/%m/%d')

# if PPID of $PPID (ie parent pid ^ 2) is /usr/bin/cron, we are run from cron.
# and thus SHELL is ALLWAYS /usr/bin/sh
# and then $PPID is crontab entry
PPPID=$( /usr/bin/ps -p $PPID -o ppid= )
PPPID_COMM=$( /usr/bin/ps -p $PPPID -o comm= )
cron=
[[ ${PPPID_COMM} = '/usr/sbin/cron' ]] && cron=" run from cron "

print "$Revision: 8026 $" | read foo version foo
print "$URL: http://svn/edb/N1/BuildAndDeploy/trunk/make/bin/list_installed_applications.sh $" | read foo url foo

datadir=/home/jn00956/data/check-logins/${ymd}
hostlist=/home/jn00955/etc/hosts.solaris
id=/home/jn00956/.ssh/id_rsa

mkdir -p ${datadir} || {
   logg "Error creating data dir '${datadir}'"
   exit 1
}

process () {
   h=$1
   ransleep=$(( RANDOM / 3200 ))
   ransleep=$(( $ransleep + 1 ))
   sleep ${ransleep}
   logg "checking host $h"
   # check tcp connect ok
   nc -zw 5 $h 22
   if [[ $? -eq 0 ]] ; then
      ssh -o 'Batchmode yes' -i ${id} -l root $h '/usr/bin/logins -axmotus' > ${datadir}/${h} 2> ${datadir}/${h}.err 
      ssh -o 'Batchmode yes' -i ${id} -l root $h '/usr/bin/passwd -sa' > ${datadir}/${h}.passwd-sa 2> ${datadir}/${h}.err 
      #scp -o 'Batchmode yes' -i ${id} -l root $h '/usr/bin/passwd -sa' > ${datadir}/${h}.passwd-sa 2> ${datadir}/${h}.err 
   else
      logg "ERR ssh to host $h"
   fi
   logg "checking host $h done"
}

logg "For all hosts, fetch /usr/bin/logins -axmotus"
for h in $(grep -v '^#' ${hostlist} | sort) ; do
#for h in amida obake akira niwa ; do
   process $h 2>&1 | sed -e "s/^/$h:   /" &
done

wait
 
stop_time=$SECONDS
let elapsed=stop_time-start_time
elapsed=$(( stop_time - start_time ))
logg "All done, exec time: $SECONDS seconds elapsed."





${parameter}
${#parameter}
${#vname[*]}
${#vname[@]}
${!vname}
${!vname[subscript]}
${!prefix*}
${parameter:-word}
${parameter:=word}
${parameter:?word}
${parameter:+word}
${parameter:offset:length}
${parameter:offset}
${parameter#pattern}
${parameter##pattern}
${parameter%pattern}
${parameter%%pattern}
${parameter/pattern/string}
${parameter//pattern/string}
${parameter/#pattern/string}
${parameter/%pattern/string}
