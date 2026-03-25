import React, { useState } from 'react';
import { Button, Card, Table, Tag, Spin, Alert } from 'antd';
import { runAllTests, printResults, type TestResult } from '../utils/apiTest';
import { PageHeader } from '../components/common';

const ApiTest: React.FC = () => {
  const [results, setResults] = useState<TestResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [tested, setTested] = useState(false);

  const handleTest = async () => {
    setLoading(true);
    setTested(true);
    const testResults = await runAllTests();
    setResults(testResults);
    printResults(testResults);
    setLoading(false);
  };

  const columns = [
    {
      title: '接口名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '请求方法',
      dataIndex: 'method',
      key: 'method',
      render: (method: string) => (
        <Tag color={method === 'GET' ? 'blue' : method === 'POST' ? 'green' : 'orange'}>
          {method}
        </Tag>
      ),
    },
    {
      title: '接口路径',
      dataIndex: 'endpoint',
      key: 'endpoint',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        if (status === 'success') return <Tag color="success">✅ 成功</Tag>;
        if (status === 'error') return <Tag color="error">❌ 失败</Tag>;
        return <Tag>⏭️ 跳过</Tag>;
      },
    },
    {
      title: '状态码',
      dataIndex: 'statusCode',
      key: 'statusCode',
      render: (code: number) => code || '-',
    },
    {
      title: '耗时',
      dataIndex: 'duration',
      key: 'duration',
      render: (duration: number) => `${duration}ms`,
    },
    {
      title: '错误信息',
      dataIndex: 'error',
      key: 'error',
      render: (error: string) => error || '-',
    },
  ];

  const successCount = results.filter(r => r.status === 'success').length;
  const errorCount = results.filter(r => r.status === 'error').length;
  const skipCount = results.filter(r => r.status === 'skipped').length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="API 接口测试"
        subtitle="测试所有后端接口的连通性和响应状态"
        category="System"
      />

      <Card>
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-medium mb-2">接口连通性测试</h3>
            <p className="text-[#999]">点击按钮开始测试所有 API 接口</p>
          </div>
          <Button
            type="primary"
            onClick={handleTest}
            loading={loading}
            className="!bg-[#1a1a1a] !border-none"
          >
            {tested ? '重新测试' : '开始测试'}
          </Button>
        </div>

        {tested && !loading && (
          <Alert
            message={`测试结果: 成功 ${successCount} 个 | 失败 ${errorCount} 个 | 跳过 ${skipCount} 个`}
            type={errorCount === 0 ? 'success' : 'warning'}
            showIcon
            className="mb-4"
          />
        )}

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Spin size="large" tip="正在测试接口..." />
          </div>
        ) : (
          tested && (
            <Table
              dataSource={results}
              columns={columns}
              rowKey="name"
              pagination={false}
              size="small"
            />
          )
        )}
      </Card>
    </div>
  );
};

export default ApiTest;
