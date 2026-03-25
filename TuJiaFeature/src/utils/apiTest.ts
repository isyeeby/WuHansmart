/**
 * API 接口测试工具
 * 用于自测主要后端接口；依赖 Vite 代理 /api 与可登录用户（默认 demo/demo123）。
 */

const API_BASE = '/api';

export interface TestResult {
  name: string;
  endpoint: string;
  method: string;
  status: 'success' | 'error' | 'skipped';
  statusCode?: number;
  response?: unknown;
  error?: string;
  duration: number;
}

let authToken: string | null = null;

async function testEndpoint(
  name: string,
  endpoint: string,
  method: string = 'GET',
  body?: unknown,
  headers: Record<string, string> = {},
  useAuth: boolean = false
): Promise<TestResult> {
  const startTime = Date.now();

  try {
    const options: RequestInit = {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
    };

    if (useAuth && authToken) {
      options.headers = {
        ...options.headers,
        Authorization: `Bearer ${authToken}`,
      };
    }

    if (body && method !== 'GET') {
      if (headers['Content-Type'] === 'application/x-www-form-urlencoded') {
        options.body = body as string;
      } else {
        options.body = JSON.stringify(body);
      }
    }

    const response = await fetch(`${API_BASE}${endpoint}`, options);
    const duration = Date.now() - startTime;

    let data: unknown;
    const contentType = response.headers.get('content-type');
    if (contentType?.includes('application/json')) {
      data = await response.json();
    } else {
      data = await response.text();
    }

    return {
      name,
      endpoint,
      method,
      status: response.ok ? 'success' : 'error',
      statusCode: response.status,
      response: data,
      duration,
    };
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    return {
      name,
      endpoint,
      method,
      status: 'error',
      error: message,
      duration: Date.now() - startTime,
    };
  }
}

/** 从列表接口取两个 unit_id，避免写死不存在的主键 */
async function fetchTwoUnitIds(): Promise<[string, string] | null> {
  try {
    const res = await fetch(`${API_BASE}/listings?page=1&size=15`);
    if (!res.ok) return null;
    const data = (await res.json()) as { items?: { unit_id: string }[] };
    const items = data.items ?? [];
    if (items.length < 2) return null;
    return [String(items[0].unit_id), String(items[1].unit_id)];
  } catch {
    return null;
  }
}

async function loginAndGetToken(): Promise<boolean> {
  try {
    const formData = new URLSearchParams();
    formData.append('username', 'demo');
    formData.append('password', 'demo123');

    const response = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData.toString(),
    });

    const text = await response.text();
    if (!text) {
      console.log('⚠️ 登录失败: 后端返回空响应');
      return false;
    }

    let data: { access_token?: string; detail?: string };
    try {
      data = JSON.parse(text) as { access_token?: string; detail?: string };
    } catch {
      console.log('⚠️ 登录失败: 后端返回非JSON数据');
      return false;
    }

    if (response.ok && data.access_token) {
      authToken = data.access_token;
      console.log('✅ 登录成功，获取到 Token');
      return true;
    }
    console.log('⚠️ 登录失败:', data.detail || '未知错误');
    return false;
  } catch (error: unknown) {
    console.log('⚠️ 登录失败:', error instanceof Error ? error.message : error);
    return false;
  }
}

function skipMany(
  items: { name: string; endpoint: string; method: string }[]
): TestResult[] {
  return items.map((i) => ({
    name: i.name,
    endpoint: i.endpoint,
    method: i.method,
    status: 'skipped',
    duration: 0,
  }));
}

export async function runAllTests(): Promise<TestResult[]> {
  const results: TestResult[] = [];
  authToken = null;

  console.log('🚀 开始 API 接口测试...\n');

  const units = await fetchTwoUnitIds();
  const u1 = units?.[0] ?? '1';
  const u2 = units?.[1] ?? '2';
  if (!units) {
    console.log('⚠️ 未能从 /listings 获取两条 unit_id，部分用例可能 404');
  }

  // —— 认证 ——
  console.log('📋 认证模块...');
  results.push(
    await testEndpoint('用户注册', '/auth/register', 'POST', {
      username: `test_${Date.now()}`,
      password: 'test123456',
    })
  );
  results.push(
    await testEndpoint(
      '用户登录',
      '/auth/login',
      'POST',
      'username=demo&password=demo123',
      { 'Content-Type': 'application/x-www-form-urlencoded' }
    )
  );

  // —— 房源 ——
  console.log('📋 房源列表...');
  results.push(await testEndpoint('获取房源列表', `/listings?page=1&size=5`));
  results.push(await testEndpoint('获取房源详情', `/listings/${encodeURIComponent(u1)}`));
  results.push(await testEndpoint('获取房源图片', `/listings/${encodeURIComponent(u1)}/gallery`));
  results.push(await testEndpoint('获取相似房源', `/listings/${encodeURIComponent(u1)}/similar`));
  results.push(await testEndpoint('获取热门房源', '/listings/hot/ranking'));

  // —— 首页 ——
  console.log('📋 首页...');
  results.push(await testEndpoint('首页统计', '/home/stats'));
  results.push(await testEndpoint('首页热门商圈', '/home/hot-districts?limit=8'));
  results.push(await testEndpoint('首页推荐', '/home/recommendations?limit=6'));
  results.push(await testEndpoint('首页热力图', '/home/heatmap'));

  // —— Dashboard ——
  console.log('📋 Dashboard...');
  results.push(await testEndpoint('核心指标', '/dashboard/summary'));
  results.push(await testEndpoint('商圈对比', '/dashboard/district-comparison'));
  results.push(await testEndpoint('KPI', '/dashboard/kpi'));
  results.push(await testEndpoint('热力图', '/dashboard/heatmap'));
  results.push(await testEndpoint('热门商圈', '/dashboard/top-districts?limit=10'));
  results.push(await testEndpoint('趋势', '/dashboard/trends?days=30'));
  results.push(await testEndpoint('预警', '/dashboard/alerts'));

  // —— 分析 ——
  console.log('📋 分析...');
  results.push(await testEndpoint('商圈列表', '/analysis/districts'));
  results.push(await testEndpoint('设施溢价', '/analysis/facility-premium'));
  results.push(await testEndpoint('价格分布', '/analysis/price-distribution?district=洪山区'));
  results.push(await testEndpoint('价格机会', '/analysis/price-opportunities?limit=10'));
  results.push(await testEndpoint('ROI排行', '/analysis/roi-ranking?limit=10'));

  // —— 标签 ——
  console.log('📋 标签...');
  results.push(await testEndpoint('标签分类', '/tags/categories'));
  results.push(await testEndpoint('热门标签', '/tags/popular'));

  // —— 推荐 ——
  console.log('📋 推荐...');
  results.push(await testEndpoint('推荐列表', '/recommend?top_k=8'));
  results.push(await testEndpoint('相似房源', `/recommend/similar/${encodeURIComponent(u1)}?top_k=5`));

  // —— 预测 ——
  console.log('📋 预测...');
  results.push(
    await testEndpoint('价格预测', '/predict/price', 'POST', {
      district: '洪山区',
      bedroom_count: 2,
      bed_count: 2,
      bathroom_count: 1,
      area: 65,
      capacity: 4,
      has_metro: true,
      has_projector: true,
    })
  );
  results.push(await testEndpoint('预测-竞品', `/predict/competitors/${encodeURIComponent(u1)}?limit=5`));
  results.push(
    await testEndpoint(
      '预测-forecast',
      `/predict/forecast?district=${encodeURIComponent('洪山区')}&room_type=${encodeURIComponent('整套房源')}&capacity=4&bedrooms=2`
    )
  );
  results.push(await testEndpoint('预测-商圈均价', '/predict/district-average/洪山区'));
  results.push(await testEndpoint('预测-趋势', '/predict/trend?district=洪山区&days=30'));
  results.push(await testEndpoint('预测-特征重要性', '/predict/feature-importance'));
  results.push(await testEndpoint('预测-行政区商圈', '/predict/district-trade-areas'));
  results.push(
    await testEndpoint('预测-因子分解', '/predict/factor-decomposition', 'POST', {
      district: '武昌区',
      bedrooms: 2,
      bed_count: 2,
      capacity: 4,
      area: 80,
    })
  );
  results.push(
    await testEndpoint('预测-竞争力', '/predict/competitiveness', 'POST', {
      district: '洪山区',
      current_price: 260,
      bedroom_count: 2,
      bed_count: 2,
      bathroom_count: 1,
      area: 70,
      capacity: 4,
    })
  );

  // —— 投资 ——
  console.log('📋 投资...');
  results.push(
    await testEndpoint('投资-计算', '/investment/calculate', 'POST', {
      district: '洪山区',
      property_price: 80,
      area_sqm: 65,
      bedroom_count: 2,
      expected_daily_price: 280,
      occupancy_rate: 0.62,
      operating_costs_monthly: 2200,
      renovation_cost: 8,
      loan_ratio: 0.5,
      loan_rate: 0.045,
      loan_years: 20,
    })
  );
  results.push(
    await testEndpoint('投资-现金流', `/investment/cashflow/${encodeURIComponent(u1)}?months=12`)
  );
  results.push(
    await testEndpoint('投资-敏感性', '/investment/sensitivity-analysis?district=洪山区&base_price=220')
  );
  results.push(await testEndpoint('投资-排行', '/investment/ranking?limit=8'));
  results.push(await testEndpoint('投资-机会', '/investment/opportunities?min_roi=8'));

  // —— 对比（无需登录部分）——
  console.log('📋 对比...');
  results.push(
    await testEndpoint(
      '对比-提交',
      '/compare/',
      'POST',
      { unit_ids: [u1, u2], comparison_type: 'full' }
    )
  );
  results.push(
    await testEndpoint('对比-快速', `/compare/quick/${encodeURIComponent(u1)}/${encodeURIComponent(u2)}`)
  );

  // —— 地理编码 ——
  console.log('📋 地理编码...');
  results.push(
    await testEndpoint(
      '地理编码',
      `/geocode/forward?q=${encodeURIComponent('武汉市洪山区珞喻路')}&limit=2`
    )
  );

  // /api/competitor 路径参数为平台 unit_id（非 my_listings 自增 id）
  results.push(
    await testEndpoint(
      '竞品情报-监控',
      `/competitor/monitoring/${encodeURIComponent(u1)}`
    )
  );

  // —— 需登录 ——
  console.log('📋 登录后接口...');
  const isLoggedIn = await loginAndGetToken();

  const authPlanned: { name: string; endpoint: string; method: string }[] = [
    { name: '用户信息', endpoint: '/user/me', method: 'GET' },
    { name: '用户偏好GET', endpoint: '/user/me/preferences', method: 'GET' },
    { name: '用户偏好PUT', endpoint: '/user/me/preferences', method: 'PUT' },
    { name: '收藏POST', endpoint: `/favorites/${encodeURIComponent(u1)}`, method: 'POST' },
    { name: '收藏列表', endpoint: '/favorites', method: 'GET' },
    { name: '我的房源列表', endpoint: '/my-listings', method: 'GET' },
    { name: '我的房源创建', endpoint: '/my-listings', method: 'POST' },
    { name: '我的房源竞品', endpoint: '/my-listings/0/competitors', method: 'GET' },
    { name: '我的房源定价', endpoint: '/my-listings/0/price-suggestion', method: 'POST' },
    { name: '对比保存', endpoint: '/compare/save', method: 'POST' },
    { name: '对比列表', endpoint: '/compare/list', method: 'GET' },
  ];

  if (!isLoggedIn) {
    results.push(...skipMany(authPlanned));
    console.log('⚠️ 跳过需登录接口（登录失败）');
  } else {
    results.push(await testEndpoint('用户信息', '/user/me', 'GET', undefined, {}, true));
    results.push(await testEndpoint('用户偏好GET', '/user/me/preferences', 'GET', undefined, {}, true));
    results.push(
      await testEndpoint(
        '用户偏好PUT',
        '/user/me/preferences',
        'PUT',
        {
          preferred_district: '洪山区',
          preferred_price_min: 100,
          preferred_price_max: 500,
        },
        {},
        true
      )
    );

    results.push(
      await testEndpoint(
        '收藏POST',
        `/favorites/${encodeURIComponent(u1)}`,
        'POST',
        undefined,
        {},
        true
      )
    );
    results.push(await testEndpoint('收藏列表', '/favorites', 'GET', undefined, {}, true));

    results.push(await testEndpoint('我的房源列表', '/my-listings', 'GET', undefined, {}, true));

    const createRes = await testEndpoint(
      '我的房源创建',
      '/my-listings',
      'POST',
      {
        title: `ApiTest房源_${Date.now()}`,
        district: '洪山区',
        business_circle: '光谷广场',
        address: '珞喻路1号',
        bedroom_count: 2,
        bed_count: 2,
        bathroom_count: 1,
        max_guests: 4,
        area: 65,
        current_price: 288,
        latitude: 30.5928,
        longitude: 114.3055,
      },
      {},
      true
    );
    results.push(createRes);

    let listingId: number | null = null;
    if (createRes.status === 'success' && createRes.response && typeof createRes.response === 'object') {
      const id = (createRes.response as { id?: number }).id;
      if (typeof id === 'number') listingId = id;
    }

    if (listingId != null) {
      results.push(
        await testEndpoint(
          '我的房源竞品',
          `/my-listings/${listingId}/competitors`,
          'GET',
          undefined,
          {},
          true
        )
      );
      results.push(
        await testEndpoint(
          '我的房源定价',
          `/my-listings/${listingId}/price-suggestion`,
          'POST',
          undefined,
          {},
          true
        )
      );
    } else {
      results.push(
        ...skipMany([
          { name: '我的房源竞品', endpoint: '/my-listings/-/competitors', method: 'GET' },
          { name: '我的房源定价', endpoint: '/my-listings/-/price-suggestion', method: 'POST' },
        ])
      );
    }

    results.push(
      await testEndpoint(
        '对比保存',
        '/compare/save',
        'POST',
        { unit_ids: [u1, u2], comparison_type: 'full' },
        {},
        true
      )
    );
    results.push(await testEndpoint('对比列表', '/compare/list', 'GET', undefined, {}, true));
  }

  const success = results.filter((r) => r.status === 'success').length;
  const error = results.filter((r) => r.status === 'error').length;
  const skipped = results.filter((r) => r.status === 'skipped').length;

  console.log(`\n📊 结果统计: 成功 ${success} | 失败 ${error} | 跳过 ${skipped}\n`);

  return results;
}

export function printResults(results: TestResult[]) {
  console.table(
    results.map((r) => ({
      接口: r.name,
      方法: r.method,
      状态: r.status === 'success' ? '✅' : r.status === 'error' ? '❌' : '⏭️',
      状态码: r.statusCode ?? '-',
      耗时: `${r.duration}ms`,
      错误: r.error ?? '-',
    }))
  );
}
