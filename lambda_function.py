import boto3
import os, sys
import json
import requests
from datetime import date, datetime, timedelta
import boto3
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal

webhook = os.environ['SLACK_WEBHOOK_URL']
dynamo_table = os.environ['DYNAMO_TABLE']

#メイン関数
def lambda_handler(event, context):
    #初期設定
    client = boto3.client('ce', region_name='ap-northeast-1')
    dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-1')
    table = dynamodb.Table(dynamo_table)

    aws_total = total_cost(client)

    dynamo_insert(dynamodb, table, aws_total)

    before_day = check_day_cost(dynamodb, table, aws_total)
    before_month = check_month_cost(dynamodb, table, aws_total)

    #Slackへの通知
    title,detail,flag = get_message(aws_total, before_day, before_month)

    post_slack(title, detail, flag)

#一日のトータルコスト
def total_cost(client):
    response = client.get_cost_and_usage(
        TimePeriod={
            'Start': get_begin_day(),
            'End': get_today()
        },
        Granularity='MONTHLY',
        Metrics=[
            'AmortizedCost'
        ]
    )

    return {
        'start': response['ResultsByTime'][0]['TimePeriod']['Start'],
        'end': response['ResultsByTime'][0]['TimePeriod']['End'],
        'billing': response['ResultsByTime'][0]['Total']['AmortizedCost']['Amount'],
    }

def get_message(total_billing, before_day, before_month):
    start = datetime.strptime(total_billing['start'], '%Y-%m-%d').strftime('%m/%d')
    end = datetime.strptime(total_billing['end'], '%Y-%m-%d').strftime('%m/%d')
    total = round(float(total_billing['billing']), 2)

    title = f'{start}～{end}の請求額は、{total:.2f} USDですにゃ。'
    detail = '前日比：' + '{:+}'.format(before_day) + '％ですにゃ\n' + '月平均比：' + '{:+}'.format(before_month) + '％ですにゃ'
    
    if before_month >= 25:
        flag = 1
    else:
        flag = 0

    return title, detail, flag

#dynamoへ書き込むタスク
def dynamo_insert(dynamodb, table, aws_total):
    total = json.loads(json.dumps(round(float(aws_total['billing']), 2)), parse_float=Decimal)
    today = datetime.today()
    month = today.month
    day = today.day

    table.put_item(
    Item={
            'Month': month,
            'Day': day,
            'Cost': total,
        }
    )

#昨日の金額
def check_day_cost(dynamodb, table, aws_total):
    total = round(float(aws_total['billing']), 2)
    total = str(total)
    total = Decimal(total)
    yesterday = datetime.today() - timedelta(days=1)
    month = yesterday.month
    day = yesterday.day

    response = table.query(
        KeyConditionExpression=Key('Month').eq(month) & Key('Day').eq(day), 
        Limit=1)
    total_yesterday = response['Items'][0]['Cost']
    Comparison = round(float((total - total_yesterday) / total_yesterday * 100), 2)
    return Comparison

#月平均
def check_month_cost(dynamodb, table, aws_total):
    total = round(float(aws_total['billing']), 2)
    total = str(total)
    total = Decimal(total)
    today = datetime.today()
    month = today.month

    response = table.query(
        KeyConditionExpression=Key('Month').eq(month))

    total_month = 0
    i = 0
    for key in response['Items']:
        total_month = total_month + key['Cost']
        i = i + 1
    
    average_month = total_month / i
    print(average_month)
    print(i)
    Comparison = round(float((total - average_month) / average_month * 100), 2)
    print(Comparison)
    return Comparison

#前日
def get_begin_day():
    today = date.today() - timedelta(days=1)
    return date(today.year, today.month, today.day).isoformat()

#今日
def get_today():
    return date.today().isoformat()

#cleate slack response
def post_slack(title, detail, flag):

    if flag == 1:
        color = '#dc143c'
    else:
        color = '#36a64f'

    payload = {
        'attachments': [
            {
                'color': color,
                'pretext': title,
                'text': detail
            }
        ]
    }
    response = requests.post(webhook, data=json.dumps(payload))

if __name__ == "__main__":
    pass