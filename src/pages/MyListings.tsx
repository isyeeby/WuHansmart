import React, { useState, useEffect } from 'react';
import { Card, List, Button, Tag, Modal, Form, Input, Select, InputNumber, Row, Col, Spin, Empty, message, Tooltip, Divider } from 'antd';
import { 
  PlusOutlined, 
  DeleteOutlined, 
  BarChartOutlined, 
  DollarOutlined,
  HomeOutlined,
  EnvironmentOutlined,
  TeamOutlined,
  ExpandOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  BulbOutlined,
  ArrowRightOutlined
} from '@ant-design/icons';
import { Link } from 'react-router-dom';
import { PageHeader } from '../components/common';
import { motion } from 'motion/react';
import { 
  getMyListings, 
  createMyListing, 
  updateMyListing,
  deleteMyListing, 
  getCompetitorAnalysis, 
  getPriceSuggestion,
  getDistrictTradeAreas,
  type MyListing,
  type CompetitorAnalysis,
  type PriceSuggestion 
} from '../services/myListingsApi';
import { getTagCategories, type TagCategory } from '../services/tagsApi';
import { LocationMapPicker } from '../components/LocationMapPicker';
import { forwardGeocode } from '../services/geocodeApi';

const { Option } = Select;

const MyListings: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [listings, setListings] = useState<MyListing[]>([]);
  const [tagCategories, setTagCategories] = useState<TagCategory[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isAnalysisModalOpen, setIsAnalysisModalOpen] = useState(false);
  const [isPriceModalOpen, setIsPriceModalOpen] = useState(false);
  const [selectedListing, setSelectedListing] = useState<MyListing | null>(null);
  const [competitorAnalysis, setCompetitorAnalysis] = useState<CompetitorAnalysis | null>(null);
  const [priceSuggestion, setPriceSuggestion] = useState<PriceSuggestion | null>(null);
  const [form] = Form.useForm();
  const [editForm] = Form.useForm();
  const createLat = Form.useWatch('latitude', form);
  const createLng = Form.useWatch('longitude', form);
  const editLat = Form.useWatch('latitude', editForm);
  const editLng = Form.useWatch('longitude', editForm);
  const [geoLoadingCreate, setGeoLoadingCreate] = useState(false);
  const [geoLoadingEdit, setGeoLoadingEdit] = useState(false);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  
  // 行政区和商圈数据
  const [districts, setDistricts] = useState<string[]>([]);
  const [tradeAreasMap, setTradeAreasMap] = useState<Record<string, string[]>>({});
  const [availableTradeAreas, setAvailableTradeAreas] = useState<string[]>([]);
  const [editAvailableTradeAreas, setEditAvailableTradeAreas] = useState<string[]>([]);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      console.log('开始获取我的房源列表...');
      const [listingsData, tagsData, districtData] = await Promise.all([
        getMyListings(),
        getTagCategories(),
        getDistrictTradeAreas(),
      ]);
      console.log('获取到的房源数据:', listingsData);
      console.log('获取到的标签数据:', tagsData);
      console.log('是否为数组:', Array.isArray(listingsData));
      console.log('数组长度:', listingsData?.length);
      const processedListings = Array.isArray(listingsData) ? listingsData : [];
      console.log('处理后的房源数据:', processedListings);
      setListings(processedListings);
      setTagCategories(Array.isArray(tagsData) ? tagsData : []);
      
      // 设置行政区和商圈数据
      setDistricts(districtData.districts || []);
      setTradeAreasMap(districtData.trade_areas || {});
    } catch (error) {
      console.error('获取数据失败:', error);
      message.error('获取数据失败');
    } finally {
      setLoading(false);
    }
  };

  const handleGeocodeCreate = async () => {
    const district = form.getFieldValue('district');
    const address = (form.getFieldValue('address') as string) || '';
    const q = ['武汉市', district, address].filter(Boolean).join(' ');
    if (q.replace(/\s/g, '').length < 4) {
      message.warning('请先填写行政区与详细地址');
      return;
    }
    setGeoLoadingCreate(true);
    try {
      const hits = await forwardGeocode(q);
      if (hits[0]) {
        form.setFieldsValue({
          latitude: hits[0].latitude,
          longitude: hits[0].longitude,
        });
        message.success('已解析坐标，可在地图上点击微调');
      }
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err?.response?.data?.detail || '解析失败，请直接点击地图选点');
    } finally {
      setGeoLoadingCreate(false);
    }
  };

  const handleGeocodeEdit = async () => {
    const district = editForm.getFieldValue('district');
    const address = (editForm.getFieldValue('address') as string) || '';
    const q = ['武汉市', district, address].filter(Boolean).join(' ');
    if (q.replace(/\s/g, '').length < 4) {
      message.warning('请先填写行政区与详细地址');
      return;
    }
    setGeoLoadingEdit(true);
    try {
      const hits = await forwardGeocode(q);
      if (hits[0]) {
        editForm.setFieldsValue({
          latitude: hits[0].latitude,
          longitude: hits[0].longitude,
        });
        message.success('已解析坐标，可在地图上点击微调');
      }
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err?.response?.data?.detail || '解析失败，请直接点击地图选点');
    } finally {
      setGeoLoadingEdit(false);
    }
  };

  const handleCreate = async (values: any) => {
    try {
      await createMyListing({
        title: values.title,
        district: values.district,
        business_circle: values.business_circle,
        address: values.address,
        latitude: values.latitude,
        longitude: values.longitude,
        bedroom_count: values.bedroom_count,
        bed_count: values.bed_count,
        bathroom_count: values.bathroom_count,
        max_guests: values.max_guests,
        area: values.area,
        current_price: values.current_price,
        style_tags: values.style_tags || [],
        facility_tags: values.facility_tags || [],
        location_tags: values.location_tags || [],
        crowd_tags: values.crowd_tags || [],
      });
      message.success('创建成功');
      setIsModalOpen(false);
      form.resetFields();
      fetchData();
    } catch (error) {
      message.error('创建失败');
    }
  };

  const handleEdit = async (values: any) => {
    if (!selectedListing) return;
    try {
      await updateMyListing(selectedListing.id, {
        title: values.title,
        district: values.district,
        business_circle: values.business_circle,
        address: values.address,
        latitude: values.latitude,
        longitude: values.longitude,
        bedroom_count: values.bedroom_count,
        bed_count: values.bed_count,
        bathroom_count: values.bathroom_count,
        max_guests: values.max_guests,
        area: values.area,
        current_price: values.current_price,
        style_tags: values.style_tags || [],
        facility_tags: values.facility_tags || [],
        location_tags: values.location_tags || [],
        crowd_tags: values.crowd_tags || [],
      });
      message.success('更新成功');
      setIsEditModalOpen(false);
      editForm.resetFields();
      setSelectedListing(null);
      fetchData();
    } catch (error) {
      message.error('更新失败');
    }
  };

  // 行政区改变时更新商圈列表（添加房源表单）
  const handleDistrictChange = (district: string) => {
    const tradeAreas = tradeAreasMap[district] || [];
    setAvailableTradeAreas(tradeAreas);
    form.setFieldsValue({ business_circle: undefined });
  };

  // 行政区改变时更新商圈列表（编辑房源表单）
  const handleEditDistrictChange = (district: string) => {
    const tradeAreas = tradeAreasMap[district] || [];
    setEditAvailableTradeAreas(tradeAreas);
    editForm.setFieldsValue({ business_circle: undefined });
  };

  const showEditModal = (listing: MyListing) => {
    setSelectedListing(listing);
    
    // 设置该行政区的商圈列表
    const tradeAreas = tradeAreasMap[listing.district] || [];
    setEditAvailableTradeAreas(tradeAreas);
    
    editForm.setFieldsValue({
      title: listing.title,
      district: listing.district,
      business_circle: listing.business_circle,
      address: listing.address,
      latitude: listing.latitude,
      longitude: listing.longitude,
      bedroom_count: listing.bedroom_count,
      bed_count: listing.bed_count,
      bathroom_count: listing.bathroom_count,
      max_guests: listing.max_guests,
      area: listing.area,
      current_price: listing.current_price,
      style_tags: listing.style_tags || [],
      facility_tags: listing.facility_tags || [],
      location_tags: listing.location_tags || [],
      crowd_tags: listing.crowd_tags || [],
    });
    setIsEditModalOpen(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteMyListing(id);
      message.success('删除成功');
      fetchData();
    } catch (error) {
      message.error('删除失败');
    }
  };

  const showAnalysis = async (listing: MyListing) => {
    setSelectedListing(listing);
    setIsAnalysisModalOpen(true);
    setAnalysisLoading(true);
    try {
      const analysis = await getCompetitorAnalysis(listing.id);
      setCompetitorAnalysis(analysis);
    } catch (error) {
      message.error('获取竞品分析失败');
    } finally {
      setAnalysisLoading(false);
    }
  };

  const showPriceSuggestion = async (listing: MyListing) => {
    setSelectedListing(listing);
    setIsPriceModalOpen(true);
    setAnalysisLoading(true);
    try {
      const suggestion = await getPriceSuggestion(listing.id);
      setPriceSuggestion(suggestion);
    } catch (error) {
      message.error('获取定价建议失败');
    } finally {
      setAnalysisLoading(false);
    }
  };

  // 获取各类标签选项
  const styleTags = tagCategories.find(c => c.category === 'style')?.tags || [];
  const facilityTags = tagCategories.find(c => c.category === 'facility')?.tags || [];
  const locationTags = tagCategories.find(c => c.category === 'location')?.tags || [];
  const serviceTags = tagCategories.find(c => c.category === 'service')?.tags || [];

  return (
    <div className="space-y-8">
      {/* 页面头部 - 禅意风格 */}
      <div className="relative">
        <PageHeader
          title="我的房源"
          subtitle="管理您的民宿房源，获取竞品分析和定价建议"
          category="My Listings"
          extra={
            <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => setIsModalOpen(true)}
                className="!bg-[#1a1a1a] !border-none !h-11 !px-6 !rounded-sm hover:!bg-[#2d2d2d] transition-all duration-300 shadow-lg hover:shadow-xl"
              >
                添加房源
              </Button>
            </motion.div>
          }
        />
        {/* 装饰线 */}
        <div className="absolute -bottom-4 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[#ebe7e0] to-transparent" />
      </div>

      {/* 房源列表 */}
      <div style={{ display: 'none' }}>调试: loading={String(loading)}, listings.length={listings.length}</div>
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <Spin size="large" tip="加载中..." />
        </div>
      ) : listings.length === 0 ? (
        <div className="text-center py-12">
          <Empty description="暂无房源数据，请添加您的第一个房源" />
        </div>
      ) : (
        <div>
          <List
            grid={{ gutter: 24, xs: 1, sm: 2, lg: 3 }}
            dataSource={listings}
            renderItem={(item) => (
              <List.Item>
                <div className="h-full">
                    <Card
                      bordered={false}
                      className="!rounded-sm !bg-white hover:shadow-xl transition-all duration-500 group overflow-hidden h-full flex flex-col"
                      style={{ 
                        boxShadow: '0 2px 20px rgba(0, 0, 0, 0.06)',
                        border: '1px solid #ebe7e0'
                      }}
                      bodyStyle={{ padding: 0, flex: 1, display: 'flex', flexDirection: 'column' }}
                    >
                      {/* 卡片头部 - 房源标题区 */}
                      <div className="relative p-5 pb-4 border-b border-[#f5f2ed]">
                        {/* 悬停时的装饰线 */}
                        <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-transparent via-[#c45c3e] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                        
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex-1 min-w-0">
                            <h3 className="font-serif text-lg font-semibold text-[#1a1a1a] line-clamp-1 group-hover:text-[#c45c3e] transition-colors duration-300">
                              {item.title}
                            </h3>
                            <div className="flex items-center gap-2 mt-2 text-sm text-[#999]">
                              <EnvironmentOutlined className="text-[#b8956e]" />
                              <span>{item.district}</span>
                              {item.business_circle && (
                                <>
                                  <span className="text-[#ebe7e0]">|</span>
                                  <span>{item.business_circle}</span>
                                </>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* 房源信息区 */}
                      <div className="p-5 space-y-4 flex-1">
                        {/* 房型信息 - 图标化展示 */}
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-1.5">
                            <div className="w-8 h-8 rounded-full bg-[#f5f2ed] flex items-center justify-center">
                              <HomeOutlined className="text-xs text-[#b8956e]" />
                            </div>
                            <span className="text-sm text-[#6b6b6b]">{item.bedroom_count}室{item.bed_count}床{item.area ? ` · ${item.area}㎡` : ''}</span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <div className="w-8 h-8 rounded-full bg-[#f5f2ed] flex items-center justify-center">
                              <TeamOutlined className="text-xs text-[#5a8a6e]" />
                            </div>
                            <span className="text-sm text-[#6b6b6b]">可住{item.max_guests}人</span>
                          </div>
                          {item.area && (
                            <div className="flex items-center gap-1.5">
                              <div className="w-8 h-8 rounded-full bg-[#f5f2ed] flex items-center justify-center">
                                <ExpandOutlined className="text-xs text-[#c45c3e]" />
                              </div>
                              <span className="text-sm text-[#6b6b6b]">{item.area}㎡</span>
                            </div>
                          )}
                        </div>

                        {/* 价格展示 */}
                        <div className="flex items-baseline gap-2 pt-2 border-t border-[#f5f2ed]">
                          <span className="text-xs text-[#999] uppercase tracking-wider">当前定价</span>
                          <span className="text-3xl font-serif font-semibold text-[#c45c3e]">
                            ¥{item.current_price}
                          </span>
                          <span className="text-sm text-[#999]">/晚</span>
                        </div>

                        {/* 创建时间 */}
                        <div className="text-xs text-[#999] flex items-center gap-1">
                          <span className="w-1 h-1 rounded-full bg-[#ebe7e0]" />
                          创建于 {new Date(item.created_at).toLocaleDateString('zh-CN')}
                        </div>
                      </div>

                      {/* 操作按钮区 */}
                      <div className="p-4 bg-[#faf8f5] border-t border-[#f5f2ed] flex gap-2">
                        <motion.div className="flex-1" whileHover={{ y: -2 }} whileTap={{ scale: 0.98 }}>
                          <Button
                            type="text"
                            icon={<BarChartOutlined />}
                            onClick={() => showAnalysis(item)}
                            className="!w-full !h-10 !bg-white !border !border-[#ebe7e0] !text-[#1a1a1a] hover:!border-[#b8956e] hover:!text-[#b8956e] transition-all duration-300 !rounded-sm"
                          >
                            竞品分析
                          </Button>
                        </motion.div>
                        <motion.div className="flex-1" whileHover={{ y: -2 }} whileTap={{ scale: 0.98 }}>
                          <Button
                            type="text"
                            icon={<DollarOutlined />}
                            onClick={() => showPriceSuggestion(item)}
                            className="!w-full !h-10 !bg-white !border !border-[#ebe7e0] !text-[#1a1a1a] hover:!border-[#c45c3e] hover:!text-[#c45c3e] transition-all duration-300 !rounded-sm"
                          >
                            定价建议
                          </Button>
                        </motion.div>
                        <motion.div whileHover={{ y: -2 }} whileTap={{ scale: 0.98 }}>
                          <Button
                            type="text"
                            onClick={() => showEditModal(item)}
                            className="!w-10 !h-10 !bg-white !border !border-[#ebe7e0] !text-[#1a1a1a] hover:!border-[#5a8a6e] hover:!text-[#5a8a6e] transition-all duration-300 !rounded-sm"
                          >
                            编辑
                          </Button>
                        </motion.div>
                        <motion.div whileHover={{ y: -2 }} whileTap={{ scale: 0.98 }}>
                          <Button
                            type="text"
                            danger
                            onClick={() => handleDelete(item.id)}
                            className="!w-10 !h-10 !bg-white !border !border-[#ebe7e0] !rounded-sm"
                          >
                            删除
                          </Button>
                        </motion.div>
                      </div>
                    </Card>
                  </div>
                </List.Item>
              )}
            />
          </div>
      )}

      {/* 添加房源弹窗 - 禅意风格 */}
      <Modal
        title={
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-[#f5f2ed] flex items-center justify-center">
              <PlusOutlined className="text-[#c45c3e]" />
            </div>
            <div>
              <div className="font-serif text-lg font-semibold text-[#1a1a1a]">添加房源</div>
              <div className="text-xs text-[#999]">填写房源基本信息</div>
            </div>
          </div>
        }
        open={isModalOpen}
        onCancel={() => {
          setIsModalOpen(false);
          form.resetFields();
        }}
        footer={null}
        width={780}
        destroyOnClose
        className="!rounded-sm"
      >
        <Divider className="!my-4 !border-[#f5f2ed]" />
        <Form form={form} layout="vertical" onFinish={handleCreate} className="pt-2">
          <Form.Item 
            name="title" 
            label={<span className="text-[#4a4a4a] font-medium">房源标题</span>} 
            rules={[{ required: true, message: '请输入房源标题' }]}
          >
            <Input 
              placeholder="例如：温馨两居室，近地铁" 
              className="!h-11 !rounded-sm !border-[#ebe7e0] hover:!border-[#b8956e] focus:!border-[#1a1a1a]"
            />
          </Form.Item>

          <Row gutter={20}>
            <Col span={12}>
              <Form.Item 
                name="district" 
                label={<span className="text-[#4a4a4a] font-medium">行政区</span>} 
                rules={[{ required: true, message: '请选择行政区' }]}
              >
                <Select 
                  placeholder="选择行政区"
                  className="!h-11"
                  dropdownStyle={{ borderRadius: '4px' }}
                  onChange={handleDistrictChange}
                >
                  {districts.map(d => (
                    <Option key={d} value={d}>{d}</Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item 
                name="business_circle" 
                label={<span className="text-[#4a4a4a] font-medium">商圈</span>}
              >
                <Select 
                  placeholder="请先选择行政区"
                  className="!h-11"
                  dropdownStyle={{ borderRadius: '4px' }}
                  allowClear
                  showSearch
                  optionFilterProp="children"
                >
                  {availableTradeAreas.map(ta => (
                    <Option key={ta} value={ta}>{ta}</Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="address"
            label={<span className="text-[#4a4a4a] font-medium">详细地址</span>}
            tooltip="填写后可「解析地址」自动定位；也可跳过，直接在地图上点击选坐标。"
          >
            <Input
              placeholder="例如：珞喻路1037号、中山大道与江汉路交汇处"
              className="!h-11 !rounded-sm !border-[#ebe7e0] hover:!border-[#b8956e] focus:!border-[#1a1a1a]"
            />
          </Form.Item>
          <div className="flex justify-end mb-3">
            <Button loading={geoLoadingCreate} onClick={() => void handleGeocodeCreate()}>
              根据地址解析坐标
            </Button>
          </div>
          <div className="mb-3">
            <div className="text-[#4a4a4a] font-medium mb-2 flex items-center gap-2">
              <EnvironmentOutlined className="text-[#5a8a6e]" />
              地图选点
            </div>
            <LocationMapPicker
              latitude={createLat}
              longitude={createLng}
              onPick={(la, lo) => form.setFieldsValue({ latitude: la, longitude: lo })}
            />
          </div>
          <Row gutter={20}>
            <Col span={12}>
              <Form.Item name="latitude" label={<span className="text-[#4a4a4a] font-medium">纬度</span>}>
                <InputNumber
                  min={-90}
                  max={90}
                  step={0.000001}
                  style={{ width: '100%' }}
                  className="!h-11 !rounded-sm"
                  placeholder="地图点击或解析自动填入"
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="longitude" label={<span className="text-[#4a4a4a] font-medium">经度</span>}>
                <InputNumber
                  min={-180}
                  max={180}
                  step={0.000001}
                  style={{ width: '100%' }}
                  className="!h-11 !rounded-sm"
                  placeholder="地图点击或解析自动填入"
                />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={20}>
            <Col span={8}>
              <Form.Item 
                name="bedroom_count" 
                label={<span className="text-[#4a4a4a] font-medium">卧室数</span>} 
                rules={[{ required: true, message: '请输入卧室数' }]}
              >
                <InputNumber 
                  min={1} 
                  max={10} 
                  style={{ width: '100%' }} 
                  className="!h-11 !rounded-sm"
                />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item 
                name="bed_count" 
                label={<span className="text-[#4a4a4a] font-medium">床位数</span>} 
                rules={[{ required: true, message: '请输入床位数' }]}
              >
                <InputNumber 
                  min={1} 
                  max={20} 
                  style={{ width: '100%' }} 
                  className="!h-11 !rounded-sm"
                />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item 
                name="bathroom_count" 
                label={<span className="text-[#4a4a4a] font-medium">卫生间数</span>} 
                rules={[{ required: true, message: '请输入卫生间数' }]}
              >
                <InputNumber 
                  min={1} 
                  max={10} 
                  style={{ width: '100%' }} 
                  className="!h-11 !rounded-sm"
                />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={20}>
            <Col span={12}>
              <Form.Item 
                name="max_guests" 
                label={<span className="text-[#4a4a4a] font-medium">可住人数</span>} 
                rules={[{ required: true, message: '请输入可住人数' }]}
              >
                <InputNumber 
                  min={1} 
                  max={20} 
                  style={{ width: '100%' }} 
                  className="!h-11 !rounded-sm"
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item 
                name="area" 
                label={<span className="text-[#4a4a4a] font-medium">面积 (㎡)</span>}
              >
                <InputNumber 
                  min={5} 
                  max={500} 
                  style={{ width: '100%' }} 
                  className="!h-11 !rounded-sm"
                />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item 
            name="current_price" 
            label={<span className="text-[#4a4a4a] font-medium">当前定价</span>} 
            rules={[{ required: true, message: '请输入当前定价' }]}
          >
            <InputNumber 
              min={1} 
              style={{ width: '100%' }} 
              prefix={<span className="text-[#c45c3e] font-medium">¥</span>}
              className="!h-11 !rounded-sm"
              placeholder="输入每晚价格"
            />
          </Form.Item>

          <Form.Item 
            name="facility_tags" 
            label={<span className="text-[#4a4a4a] font-medium">设施标签（与智能定价一致）</span>}
            tooltip="选项与定价工作台识别口径一致，保存后在「智能定价」选本房源可自动勾选对应项"
          >
            <Select 
              mode="multiple" 
              placeholder="选择设施"
              className="!min-h-11"
              tagRender={(props) => (
                <Tag 
                  className="!bg-[#f5f2ed] !border-[#ebe7e0] !text-[#6b6b6b] !rounded-sm"
                  closable={props.closable}
                  onClose={props.onClose}
                >
                  {props.label}
                </Tag>
              )}
            >
              {facilityTags.map((tag: any) => {
                const tagValue = typeof tag === 'string' ? tag : tag.text || tag.tagText || String(tag);
                return <Option key={tagValue} value={tagValue}>{tagValue}</Option>;
              })}
            </Select>
          </Form.Item>

          <Form.Item 
            name="location_tags" 
            label={<span className="text-[#4a4a4a] font-medium">位置与环境（与智能定价一致）</span>}
            tooltip="含近地铁、景观等；选「江景/江景房」等均会映射到定价页景观勾选"
          >
            <Select 
              mode="multiple" 
              placeholder="选择位置特点"
              className="!min-h-11"
              tagRender={(props) => (
                <Tag 
                  className="!bg-[#f5f2ed] !border-[#ebe7e0] !text-[#6b6b6b] !rounded-sm"
                  closable={props.closable}
                  onClose={props.onClose}
                >
                  {props.label}
                </Tag>
              )}
            >
              {locationTags.map((tag: any) => {
                const tagValue = typeof tag === 'string' ? tag : tag.text || tag.tagText || String(tag);
                return <Option key={tagValue} value={tagValue}>{tagValue}</Option>;
              })}
            </Select>
          </Form.Item>

          <Form.Item
            name="style_tags"
            label={<span className="text-[#4a4a4a] font-medium">风格标签</span>}
          >
            <Select
              mode="multiple"
              placeholder="选择风格"
              className="!min-h-11"
              tagRender={(props) => (
                <Tag
                  className="!bg-[#f5f2ed] !border-[#ebe7e0] !text-[#6b6b6b] !rounded-sm"
                  closable={props.closable}
                  onClose={props.onClose}
                >
                  {props.label}
                </Tag>
              )}
            >
              {styleTags.map((tag: any) => {
                const tagValue = typeof tag === 'string' ? tag : tag.text || tag.tagText || String(tag);
                return <Option key={tagValue} value={tagValue}>{tagValue}</Option>;
              })}
            </Select>
          </Form.Item>

          <Form.Item
            name="crowd_tags"
            label={<span className="text-[#4a4a4a] font-medium">服务 / 人群（与智能定价一致）</span>}
            tooltip="如可带宠物、亲子精选等，会映射到定价页「可带宠物」等选项"
          >
            <Select
              mode="multiple"
              placeholder="选择服务或人群"
              className="!min-h-11"
              tagRender={(props) => (
                <Tag
                  className="!bg-[#f5f2ed] !border-[#ebe7e0] !text-[#6b6b6b] !rounded-sm"
                  closable={props.closable}
                  onClose={props.onClose}
                >
                  {props.label}
                </Tag>
              )}
            >
              {serviceTags.map((tag: any) => {
                const tagValue = typeof tag === 'string' ? tag : tag.text || tag.tagText || String(tag);
                return <Option key={tagValue} value={tagValue}>{tagValue}</Option>;
              })}
            </Select>
          </Form.Item>

          <Form.Item className="!mb-0 !mt-6">
            <Button
              type="primary"
              htmlType="submit"
              block
              className="!bg-[#1a1a1a] !border-none !h-12 !rounded-sm hover:!bg-[#2d2d2d] transition-all duration-300"
            >
              创建房源
            </Button>
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑房源弹窗 - 禅意风格 */}
      <Modal
        title={
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-[#f5f2ed] flex items-center justify-center">
              <HomeOutlined className="text-[#5a8a6e]" />
            </div>
            <div>
              <div className="font-serif text-lg font-semibold text-[#1a1a1a]">编辑房源</div>
              <div className="text-xs text-[#999]">{selectedListing?.title}</div>
            </div>
          </div>
        }
        open={isEditModalOpen}
        onCancel={() => {
          setIsEditModalOpen(false);
          editForm.resetFields();
          setSelectedListing(null);
        }}
        footer={null}
        width={780}
        destroyOnClose
        className="!rounded-sm"
      >
        <Divider className="!my-4 !border-[#f5f2ed]" />
        <Form form={editForm} layout="vertical" onFinish={handleEdit} className="pt-2">
          <Form.Item
            name="title"
            label={<span className="text-[#4a4a4a] font-medium">房源标题</span>}
            rules={[{ required: true, message: '请输入房源标题' }]}
          >
            <Input
              placeholder="例如：温馨两居室，近地铁"
              className="!h-11 !rounded-sm !border-[#ebe7e0] hover:!border-[#b8956e] focus:!border-[#1a1a1a]"
            />
          </Form.Item>

          <Row gutter={20}>
            <Col span={12}>
              <Form.Item
                name="district"
                label={<span className="text-[#4a4a4a] font-medium">行政区</span>}
                rules={[{ required: true, message: '请选择行政区' }]}
              >
                <Select
                  placeholder="选择行政区"
                  className="!h-11"
                  dropdownStyle={{ borderRadius: '4px' }}
                  onChange={handleEditDistrictChange}
                >
                  {districts.map(d => (
                    <Option key={d} value={d}>{d}</Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="business_circle"
                label={<span className="text-[#4a4a4a] font-medium">商圈</span>}
              >
                <Select
                  placeholder="请先选择行政区"
                  className="!h-11"
                  dropdownStyle={{ borderRadius: '4px' }}
                  allowClear
                  showSearch
                  optionFilterProp="children"
                >
                  {editAvailableTradeAreas.map(ta => (
                    <Option key={ta} value={ta}>{ta}</Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="address"
            label={<span className="text-[#4a4a4a] font-medium">详细地址</span>}
            tooltip="填写后可「解析地址」自动定位；也可直接在地图上点击选坐标。"
          >
            <Input
              placeholder="例如：珞喻路1037号"
              className="!h-11 !rounded-sm !border-[#ebe7e0] hover:!border-[#b8956e] focus:!border-[#1a1a1a]"
            />
          </Form.Item>
          <div className="flex justify-end mb-3">
            <Button loading={geoLoadingEdit} onClick={() => void handleGeocodeEdit()}>
              根据地址解析坐标
            </Button>
          </div>
          <div className="mb-3">
            <div className="text-[#4a4a4a] font-medium mb-2 flex items-center gap-2">
              <EnvironmentOutlined className="text-[#5a8a6e]" />
              地图选点
            </div>
            <LocationMapPicker
              latitude={editLat}
              longitude={editLng}
              onPick={(la, lo) => editForm.setFieldsValue({ latitude: la, longitude: lo })}
            />
          </div>
          <Row gutter={20}>
            <Col span={12}>
              <Form.Item name="latitude" label={<span className="text-[#4a4a4a] font-medium">纬度</span>}>
                <InputNumber
                  min={-90}
                  max={90}
                  step={0.000001}
                  style={{ width: '100%' }}
                  className="!h-11 !rounded-sm"
                  placeholder="地图点击或解析自动填入"
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="longitude" label={<span className="text-[#4a4a4a] font-medium">经度</span>}>
                <InputNumber
                  min={-180}
                  max={180}
                  step={0.000001}
                  style={{ width: '100%' }}
                  className="!h-11 !rounded-sm"
                  placeholder="地图点击或解析自动填入"
                />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={20}>
            <Col span={8}>
              <Form.Item
                name="bedroom_count"
                label={<span className="text-[#4a4a4a] font-medium">卧室数</span>}
                rules={[{ required: true, message: '请输入卧室数' }]}
              >
                <InputNumber
                  min={1}
                  max={10}
                  style={{ width: '100%' }}
                  className="!h-11 !rounded-sm"
                />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="bed_count"
                label={<span className="text-[#4a4a4a] font-medium">床位数</span>}
                rules={[{ required: true, message: '请输入床位数' }]}
              >
                <InputNumber
                  min={1}
                  max={20}
                  style={{ width: '100%' }}
                  className="!h-11 !rounded-sm"
                />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="bathroom_count"
                label={<span className="text-[#4a4a4a] font-medium">卫生间数</span>}
                rules={[{ required: true, message: '请输入卫生间数' }]}
              >
                <InputNumber
                  min={1}
                  max={10}
                  style={{ width: '100%' }}
                  className="!h-11 !rounded-sm"
                />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={20}>
            <Col span={12}>
              <Form.Item
                name="max_guests"
                label={<span className="text-[#4a4a4a] font-medium">可住人数</span>}
                rules={[{ required: true, message: '请输入可住人数' }]}
              >
                <InputNumber
                  min={1}
                  max={20}
                  style={{ width: '100%' }}
                  className="!h-11 !rounded-sm"
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="area"
                label={<span className="text-[#4a4a4a] font-medium">面积 (㎡)</span>}
              >
                <InputNumber
                  min={5}
                  max={500}
                  style={{ width: '100%' }}
                  className="!h-11 !rounded-sm"
                />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="current_price"
            label={<span className="text-[#4a4a4a] font-medium">当前定价</span>}
            rules={[{ required: true, message: '请输入当前定价' }]}
          >
            <InputNumber
              min={1}
              style={{ width: '100%' }}
              prefix={<span className="text-[#c45c3e] font-medium">¥</span>}
              className="!h-11 !rounded-sm"
              placeholder="输入每晚价格"
            />
          </Form.Item>

          <Form.Item
            name="style_tags"
            label={<span className="text-[#4a4a4a] font-medium">风格标签</span>}
          >
            <Select
              mode="multiple"
              placeholder="选择风格"
              className="!min-h-11"
              tagRender={(props) => (
                <Tag
                  className="!bg-[#f5f2ed] !border-[#ebe7e0] !text-[#6b6b6b] !rounded-sm"
                  closable={props.closable}
                  onClose={props.onClose}
                >
                  {props.label}
                </Tag>
              )}
            >
              {styleTags.map((tag: any) => {
                const tagValue = typeof tag === 'string' ? tag : tag.text || tag.tagText || String(tag);
                return <Option key={tagValue} value={tagValue}>{tagValue}</Option>;
              })}
            </Select>
          </Form.Item>

          <Form.Item
            name="facility_tags"
            label={<span className="text-[#4a4a4a] font-medium">设施标签（与智能定价一致）</span>}
            tooltip="与定价工作台勾选口径一致"
          >
            <Select
              mode="multiple"
              placeholder="选择设施"
              className="!min-h-11"
              tagRender={(props) => (
                <Tag
                  className="!bg-[#f5f2ed] !border-[#ebe7e0] !text-[#6b6b6b] !rounded-sm"
                  closable={props.closable}
                  onClose={props.onClose}
                >
                  {props.label}
                </Tag>
              )}
            >
              {facilityTags.map((tag: any) => {
                const tagValue = typeof tag === 'string' ? tag : tag.text || tag.tagText || String(tag);
                return <Option key={tagValue} value={tagValue}>{tagValue}</Option>;
              })}
            </Select>
          </Form.Item>

          <Form.Item
            name="location_tags"
            label={<span className="text-[#4a4a4a] font-medium">位置与环境（与智能定价一致）</span>}
            tooltip="含近地铁、江景/江景房等，会映射到定价页"
          >
            <Select
              mode="multiple"
              placeholder="选择位置特点"
              className="!min-h-11"
              tagRender={(props) => (
                <Tag
                  className="!bg-[#f5f2ed] !border-[#ebe7e0] !text-[#6b6b6b] !rounded-sm"
                  closable={props.closable}
                  onClose={props.onClose}
                >
                  {props.label}
                </Tag>
              )}
            >
              {locationTags.map((tag: any) => {
                const tagValue = typeof tag === 'string' ? tag : tag.text || tag.tagText || String(tag);
                return <Option key={tagValue} value={tagValue}>{tagValue}</Option>;
              })}
            </Select>
          </Form.Item>

          <Form.Item
            name="crowd_tags"
            label={<span className="text-[#4a4a4a] font-medium">服务 / 人群（与智能定价一致）</span>}
            tooltip="如可带宠物、亲子精选等"
          >
            <Select
              mode="multiple"
              placeholder="选择适合人群"
              className="!min-h-11"
              tagRender={(props) => (
                <Tag
                  className="!bg-[#f5f2ed] !border-[#ebe7e0] !text-[#6b6b6b] !rounded-sm"
                  closable={props.closable}
                  onClose={props.onClose}
                >
                  {props.label}
                </Tag>
              )}
            >
              {serviceTags.map((tag: any) => {
                const tagValue = typeof tag === 'string' ? tag : tag.text || tag.tagText || String(tag);
                return <Option key={tagValue} value={tagValue}>{tagValue}</Option>;
              })}
            </Select>
          </Form.Item>

          <Form.Item className="!mb-0 !mt-6">
            <Button
              type="primary"
              htmlType="submit"
              block
              className="!bg-[#1a1a1a] !border-none !h-12 !rounded-sm hover:!bg-[#2d2d2d] transition-all duration-300"
            >
              保存修改
            </Button>
          </Form.Item>
        </Form>
      </Modal>

      {/* 竞品分析弹窗 - 禅意风格 */}
      <Modal
        title={
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-[#f5f2ed] flex items-center justify-center">
              <BarChartOutlined className="text-[#b8956e]" />
            </div>
            <div>
              <div className="font-serif text-lg font-semibold text-[#1a1a1a]">竞品分析</div>
              <div className="text-xs text-[#999]">{selectedListing?.title}</div>
            </div>
          </div>
        }
        open={isAnalysisModalOpen}
        onCancel={() => setIsAnalysisModalOpen(false)}
        footer={null}
        width={820}
        className="!rounded-sm"
      >
        <Divider className="!my-4 !border-[#f5f2ed]" />
        <Spin spinning={analysisLoading} size="large">
          {competitorAnalysis && selectedListing && (
            <motion.div 
              className="space-y-6 pt-2"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.4 }}
            >
              {/* 当前房源信息卡片 */}
              <div className="bg-[#1a1a1a] text-white p-5 rounded-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs text-[#999] mb-1">正在分析房源</div>
                    <div className="font-serif text-xl font-semibold">{selectedListing.title}</div>
                    <div className="text-sm text-[#b8956e] mt-1">
                      {selectedListing.district} · {selectedListing.bedroom_count}室{selectedListing.bed_count}床 · ¥{selectedListing.current_price}/晚
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-3xl font-serif font-semibold text-[#c45c3e]">
                      ¥{selectedListing.current_price}
                    </div>
                    <div className="text-xs text-[#999]">当前定价</div>
                  </div>
                </div>
              </div>

              {/* 市场定位卡片 */}
              <div className="bg-gradient-to-br from-[#faf8f5] to-[#f5f2ed] p-6 rounded-sm border border-[#ebe7e0]">
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-1 h-4 bg-[#c45c3e] rounded-full" />
                  <span className="text-xs uppercase tracking-[0.15em] text-[#999] font-medium">市场定位</span>
                </div>
                <div className="grid grid-cols-3 gap-6">
                  <div className="text-center">
                    <div className="text-3xl font-serif font-semibold text-[#1a1a1a]">
                      {competitorAnalysis.market_position.my_price_rank}
                    </div>
                    <div className="text-xs text-[#999] mt-1">价格排名</div>
                  </div>
                  <div className="text-center border-x border-[#ebe7e0]">
                    <div className="text-3xl font-serif font-semibold text-[#b8956e]">
                      {competitorAnalysis?.market_position?.price_percentile?.toFixed(1) ?? '-'}%
                    </div>
                    <div className="text-xs text-[#999] mt-1">价格分位</div>
                  </div>
                  <div className="text-center">
                    <div className="text-3xl font-serif font-semibold text-[#5a8a6e]">
                      ¥{competitorAnalysis?.market_position?.avg_price?.toFixed(0) ?? '-'}
                    </div>
                    <div className="text-xs text-[#999] mt-1">商圈均价</div>
                  </div>
                </div>
              </div>

              {/* 分析结论 */}
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <div className="w-1 h-4 bg-[#b8956e] rounded-full" />
                  <span className="text-xs uppercase tracking-[0.15em] text-[#999] font-medium">分析结论</span>
                </div>
                
                <div className="grid grid-cols-3 gap-4">
                  {/* 优势 */}
                  <div className="bg-[rgba(90,138,110,0.05)] p-4 rounded-sm border border-[rgba(90,138,110,0.15)]">
                    <div className="flex items-center gap-2 mb-3">
                      <CheckCircleOutlined className="text-[#5a8a6e]" />
                      <span className="text-sm font-medium text-[#5a8a6e]">优势</span>
                    </div>
                    <ul className="space-y-2">
                      {competitorAnalysis.analysis.advantages.map((adv, idx) => (
                        <li key={idx} className="text-xs text-[#6b6b6b] flex items-start gap-2">
                          <span className="w-1 h-1 rounded-full bg-[#5a8a6e] mt-1.5 flex-shrink-0" />
                          {adv}
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* 劣势 */}
                  <div className="bg-[rgba(196,92,62,0.05)] p-4 rounded-sm border border-[rgba(196,92,62,0.15)]">
                    <div className="flex items-center gap-2 mb-3">
                      <CloseCircleOutlined className="text-[#c45c3e]" />
                      <span className="text-sm font-medium text-[#c45c3e]">劣势</span>
                    </div>
                    <ul className="space-y-2">
                      {competitorAnalysis.analysis.disadvantages.map((dis, idx) => (
                        <li key={idx} className="text-xs text-[#6b6b6b] flex items-start gap-2">
                          <span className="w-1 h-1 rounded-full bg-[#c45c3e] mt-1.5 flex-shrink-0" />
                          {dis}
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* 建议 */}
                  <div className="bg-[rgba(184,149,110,0.05)] p-4 rounded-sm border border-[rgba(184,149,110,0.15)]">
                    <div className="flex items-center gap-2 mb-3">
                      <BulbOutlined className="text-[#b8956e]" />
                      <span className="text-sm font-medium text-[#b8956e]">建议</span>
                    </div>
                    <ul className="space-y-2">
                      {competitorAnalysis.analysis.suggestions.map((sug, idx) => (
                        <li key={idx} className="text-xs text-[#6b6b6b] flex items-start gap-2">
                          <span className="w-1 h-1 rounded-full bg-[#b8956e] mt-1.5 flex-shrink-0" />
                          {sug}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>

              {/* 相似竞品 */}
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <div className="w-1 h-4 bg-[#1a1a1a] rounded-full" />
                  <span className="text-xs uppercase tracking-[0.15em] text-[#999] font-medium">相似竞品</span>
                </div>
                <div className="space-y-3">
                  {competitorAnalysis.competitors.map((item, idx) => (
                    <motion.div
                      key={idx}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.1 }}
                      className="flex items-center justify-between p-4 bg-[#faf8f5] rounded-sm border border-[#f5f2ed] hover:border-[#ebe7e0] transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-white flex items-center justify-center text-xs font-medium text-[#999]">
                          {idx + 1}
                        </div>
                        <span className="text-sm text-[#1a1a1a] font-medium">{item.title}</span>
                      </div>
                      <div className="flex items-center gap-6">
                        <div className="text-right">
                          <div className="text-sm font-medium text-[#c45c3e]">¥{item.final_price}</div>
                          <div className="text-xs text-[#999]">每晚</div>
                        </div>
                        <div className="flex items-center gap-1 text-[#b8956e]">
                          <span>★</span>
                          <span className="text-sm">{item.rating}</span>
                        </div>
                        <Tag className="!bg-[#f5f2ed] !border-[#ebe7e0] !text-[#6b6b6b] !text-xs">
                          相似度 {Math.round(item.similarity_score)}%
                        </Tag>
                      </div>
                    </motion.div>
                  ))}
                </div>
              </div>
            </motion.div>
          )}
        </Spin>
      </Modal>

      {/* 定价建议弹窗 - 禅意风格 */}
      <Modal
        title={
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-[#f5f2ed] flex items-center justify-center">
              <DollarOutlined className="text-[#c45c3e]" />
            </div>
            <div>
              <div className="font-serif text-lg font-semibold text-[#1a1a1a]">定价建议</div>
              <div className="text-xs text-[#999]">{selectedListing?.title}</div>
            </div>
          </div>
        }
        open={isPriceModalOpen}
        onCancel={() => setIsPriceModalOpen(false)}
        footer={null}
        width={560}
        className="!rounded-sm"
      >
        <Divider className="!my-4 !border-[#f5f2ed]" />
        <p className="mb-3 text-xs leading-relaxed text-[#999]">
          参考价与「智能定价」中的<strong className="text-[#6b6b6b]">模型基准价</strong>
          一致（日级 XGBoost 对锚定日的建议价）；不可用则回退行政区样本均价。查看未来 14
          天逐日价格与趋势请前往
          <Link to="/prediction" className="mx-0.5 text-[#c45c3e] underline-offset-2 hover:underline">
            智能定价
          </Link>
          。具体依据见下方说明。
        </p>
        <Spin spinning={analysisLoading} size="large">
          {priceSuggestion && selectedListing && (
            <motion.div 
              className="space-y-6 pt-2"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.4 }}
            >
              {/* 当前房源信息 */}
              <div className="bg-[#1a1a1a] text-white p-4 rounded-sm">
                <div className="text-xs text-[#999] mb-1">正在为以下房源定价</div>
                <div className="font-serif text-lg font-semibold">{selectedListing.title}</div>
                <div className="text-sm text-[#b8956e]">
                  {selectedListing.district} · {selectedListing.bedroom_count}室{selectedListing.bed_count}床
                </div>
              </div>

              {/* 建议价格展示 */}
              <div className="relative overflow-hidden bg-gradient-to-br from-[#faf8f5] to-[#f5f2ed] p-8 rounded-sm border border-[#ebe7e0]">
                {/* 装饰背景 */}
                <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-[rgba(196,92,62,0.05)] to-transparent rounded-full -translate-y-1/2 translate-x-1/2" />
                
                <div className="relative text-center">
                  <div className="text-xs uppercase tracking-[0.2em] text-[#999] mb-3">AI 建议价格</div>
                  <div className="flex items-baseline justify-center gap-1">
                    <span className="text-2xl text-[#c45c3e] font-serif">¥</span>
                    <span className="text-5xl font-serif font-semibold text-[#c45c3e]">
                      {priceSuggestion?.suggested_price?.toFixed(0) ?? '-'}
                    </span>
                    <span className="text-lg text-[#999] ml-1">/晚</span>
                  </div>
                  <div className="mt-4">
                    <Tag 
                      className={`!px-4 !py-1 !text-sm !rounded-sm !border-none ${
                        priceSuggestion.suggestion.includes('涨') 
                          ? '!bg-[#c45c3e] !text-white' 
                          : priceSuggestion.suggestion.includes('降')
                          ? '!bg-[#5a8a6e] !text-white'
                          : '!bg-[#b8956e] !text-white'
                      }`}
                    >
                      {priceSuggestion.suggestion.includes('涨') && <ArrowUpOutlined className="mr-1" />}
                      {priceSuggestion.suggestion.includes('降') && <ArrowDownOutlined className="mr-1" />}
                      {priceSuggestion.suggestion}
                    </Tag>
                  </div>
                </div>
              </div>

              {/* 价格对比 */}
              <div className="grid grid-cols-2 gap-4">
                <div className="text-center p-5 bg-white rounded-sm border border-[#ebe7e0]">
                  <div className="flex items-center justify-center gap-2 mb-2">
                    <div className="w-6 h-6 rounded-full bg-[#f5f2ed] flex items-center justify-center">
                      <span className="text-xs text-[#999]">现</span>
                    </div>
                    <span className="text-xs text-[#999] uppercase tracking-wider">当前价格</span>
                  </div>
                  <div className="text-2xl font-serif font-semibold text-[#1a1a1a]">
                    ¥{priceSuggestion.current_price}
                  </div>
                </div>
                <div className="text-center p-5 bg-white rounded-sm border border-[#ebe7e0]">
                  <div className="flex items-center justify-center gap-2 mb-2">
                    <div className="w-6 h-6 rounded-full bg-[#f5f2ed] flex items-center justify-center">
                      <ArrowRightOutlined className="text-xs text-[#999]" />
                    </div>
                    <span className="text-xs text-[#999] uppercase tracking-wider">价格差异</span>
                  </div>
                  <div className={`text-2xl font-serif font-semibold ${
                    priceSuggestion.price_difference > 0 
                      ? 'text-[#c45c3e]' 
                      : priceSuggestion.price_difference < 0 
                      ? 'text-[#5a8a6e]' 
                      : 'text-[#999]'
                  }`}>
                    {priceSuggestion.price_difference > 0 ? '+' : ''}
                    ¥{Math.abs(priceSuggestion.price_difference)}
                  </div>
                </div>
              </div>

              {/* 建议理由 */}
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <div className="w-1 h-4 bg-[#b8956e] rounded-full" />
                  <span className="text-xs uppercase tracking-[0.15em] text-[#999] font-medium">建议理由</span>
                </div>
                <div className="space-y-2">
                  {priceSuggestion.reasoning.map((reason, idx) => (
                    <motion.div
                      key={idx}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.1 }}
                      className="flex items-start gap-3 p-3 bg-[#faf8f5] rounded-sm"
                    >
                      <div className="w-5 h-5 rounded-full bg-white flex items-center justify-center flex-shrink-0 mt-0.5 border border-[#ebe7e0]">
                        <span className="text-xs text-[#b8956e] font-medium">{idx + 1}</span>
                      </div>
                      <span className="text-sm text-[#6b6b6b] leading-relaxed">{reason}</span>
                    </motion.div>
                  ))}
                </div>
              </div>

              {/* 置信度 */}
              <div className="flex items-center justify-between p-4 bg-gradient-to-r from-[#f5f2ed] to-transparent rounded-sm">
                <span className="text-sm text-[#6b6b6b]">预测置信度</span>
                <div className="flex items-center gap-2">
                  <div className="w-24 h-2 bg-[#ebe7e0] rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-gradient-to-r from-[#5a8a6e] to-[#b8956e] rounded-full"
                      style={{ width: `${priceSuggestion.confidence * 100}%` }}
                    />
                  </div>
                  <span className="text-sm font-medium text-[#1a1a1a]">
                    {((priceSuggestion?.confidence ?? 0) * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
            </motion.div>
          )}
        </Spin>
      </Modal>
    </div>
  );
};

export default MyListings;
