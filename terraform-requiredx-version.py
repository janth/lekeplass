#!/usr/bin/env python3

import os
import sys
import pprint
import hcl2

flist = sys.argv
flist.pop(0)

for f in flist:
  # print(f"{f}")
  with open(f, 'r') as file:
      try:
        dict = hcl2.load(file)
        # pprint.pp(dict)
        try:
          terraform = dict['terraform'][0]
          # pprint.pp(terraform)
          try:
            required_providers = terraform['required_providers'][0]
            try:
              aws = required_providers['aws']
              if aws['source'] == 'hashicorp/aws':
                print(f"{f}: {aws['source']} {aws['version']}")
                # pprint.pp(aws['version'])
            except KeyError:
              pass
          except KeyError:
            pass
        except KeyError:
          pass
      except Exception as e:
        print(f"# Error parsing file {f}")
        pass
