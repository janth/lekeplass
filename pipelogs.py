#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
import logging
import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def run_git(cmd_args):
    try:
        out = subprocess.check_output(cmd_args, stderr=subprocess.DEVNULL)
        return out.decode().strip()
    except Exception:
        return None


def get_repo_name():
    # Prefer repository directory name
    top = run_git(['git', 'rev-parse', '--show-toplevel'])
    if top:
        return os.path.basename(top)
    # Fallback to parsing remote URL
    url = run_git(['git', 'remote', 'get-url', 'origin'])
    if url:
        # handle git@github.com:owner/repo.git and https://.../owner/repo.git
        name = url.rstrip('/').split('/')[-1]
        if name.endswith('.git'):
            name = name[:-4]
        return name
    raise RuntimeError('Could not determine repository name')


def get_short_hash():
    sha = run_git(['git', 'rev-parse', '--short', 'HEAD'])
    if not sha:
        raise RuntimeError('Could not get git short hash')
    return sha


def assume_role(account, role, region, session_name='pipelogs-session'):
    role_arn = f'arn:aws:iam::{account}:role/{role}'
    logging.info('Assuming role %s', role_arn)
    sts = boto3.client('sts', region_name=region)
    resp = sts.assume_role(RoleArn=role_arn, RoleSessionName=session_name)
    creds = resp['Credentials']
    session = boto3.Session(
        aws_access_key_id=creds['AccessKeyId'],
        aws_secret_access_key=creds['SecretAccessKey'],
        aws_session_token=creds['SessionToken'],
        region_name=region,
    )
    return session


def find_execution_id(codepipeline, pipeline_name, short_hash):
    logging.info('Searching executions for pipeline %s', pipeline_name)
    next_token = None
    while True:
        params = {'pipelineName': pipeline_name, 'maxResults': 50}
        if next_token:
            params['nextToken'] = next_token
        resp = codepipeline.list_pipeline_executions(**params)
        for summary in resp.get('pipelineExecutionSummaries', []):
            exec_id = summary.get('pipelineExecutionId') or summary.get('pipelineExecutionId')
            if not exec_id:
                continue
            try:
                detail = codepipeline.get_pipeline_execution(pipelineName=pipeline_name, pipelineExecutionId=exec_id)
            except ClientError:
                continue
            pe = detail.get('pipelineExecution', {})
            for rev in pe.get('artifactRevisions', []):
                if short_hash in rev.get('revisionId', '') or short_hash in rev.get('revisionSummary', ''):
                    logging.info('Matched execution id %s for revision %s', exec_id, short_hash)
                    return exec_id
        next_token = resp.get('nextToken')
        if not next_token:
            break
    return None


def find_planlog_key(s3_client, bucket, pipeline_name, execution_id, short_hash):
    prefixes = [f'{pipeline_name}/', f'{short_hash}/', '']
    for prefix in prefixes:
        paginator = s3_client.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get('Contents', []):
                key = obj['Key']
                kl = key.lower()
                if 'planlog' in kl and (execution_id in key or short_hash in key or pipeline_name in key):
                    logging.info('Found PlanLog at s3://%s/%s', bucket, key)
                    return key
    return None


def download_and_print_s3(s3_client, bucket, key):
    logging.info('Downloading s3://%s/%s', bucket, key)
    resp = s3_client.get_object(Bucket=bucket, Key=key)
    data = resp['Body'].read()
    try:
        text = data.decode('utf-8')
    except Exception:
        text = data.decode('latin-1')
    print(text)


def main():
    p = argparse.ArgumentParser(description='Fetch PlanLog for the pipeline execution that matches the last commit short hash')
    p.add_argument('--account', required=True, help='AWS account id to assume')
    p.add_argument('--role', required=True, help='IAM role name to assume in the account')
    p.add_argument('--bucket', required=True, help='S3 bucket name where PlanLog is stored')
    p.add_argument('--region', default=os.environ.get('AWS_REGION', 'us-east-1'))
    p.add_argument('--pipeline', help='Pipeline name (defaults to <repo>-plan-pr)')
    args = p.parse_args()

    try:
        repo = get_repo_name()
        short = get_short_hash()
    except Exception as e:
        logging.error(str(e))
        sys.exit(2)

    pipeline_name = args.pipeline or f'{repo}-plan-pr'
    logging.info('Repo: %s, short hash: %s, pipeline: %s', repo, short, pipeline_name)

    try:
        session = assume_role(args.account, args.role, args.region)
    except ClientError as e:
        logging.error('Failed to assume role: %s', e)
        sys.exit(3)

    cp = session.client('codepipeline', region_name=args.region)
    exec_id = find_execution_id(cp, pipeline_name, short)
    if not exec_id:
        logging.error('No pipeline execution found for commit %s', short)
        sys.exit(4)

    s3 = session.client('s3', region_name=args.region)
    key = find_planlog_key(s3, args.bucket, pipeline_name, exec_id, short)
    if not key:
        logging.error('Could not find PlanLog in bucket %s for execution %s', args.bucket, exec_id)
        sys.exit(5)

    download_and_print_s3(s3, args.bucket, key)


if __name__ == '__main__':
    main()
