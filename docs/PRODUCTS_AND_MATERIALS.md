# V0.7.0 产品中心与素材库说明

## 功能边界

V0.7.0 用于维护企业产品、案例和销售资料，并把已发布产品推荐到员工数字名片。当前版本不包含库存、促销价格、购物车、订单和支付。

## 产品与分类

- 产品分类按企业隔离，分类编号在企业内唯一，支持排序和停用；
- 产品包含名称、分类、摘要、介绍、规格、封面、图集、视频、PDF 附件和排序值；
- 产品状态为草稿、已发布或已下线；已发布产品不能退回草稿，只能下线后再次发布；
- 发布要求至少存在公开封面及摘要或介绍，关联分类必须启用；
- 已发布产品再次编辑时仍会执行完整公开性校验，不能换成私有素材。

管理端 `/company/products` 对具有 `product.read` 的用户开放。普通员工默认以只读方式浏览，不请求素材库接口，也不显示新增、编辑、发布和下线操作；管理操作要求 `product.manage`。

## 企业素材库

素材支持 JPEG、PNG、WebP、MP4、WebM 和 PDF。服务端同时校验扩展名、MIME 类型、文件内容签名和配置的大小上限：

- 图片默认不超过 10 MB；
- 视频默认不超过 100 MB；
- PDF 默认不超过 30 MB。

上传使用临时文件，完整校验并落盘后才创建数据库记录。失败时删除临时文件，避免无业务归属的脏数据。素材分为公开和私有；只有公开素材能被已发布产品使用。已被产品引用的素材不可删除，已被已发布产品引用的素材不可改为私有。

管理端入口为 `/company/materials`，查看要求 `material.read`，上传、修改访问范围和删除要求 `material.manage`。

## 名片推荐与公开快照

员工或名片管理员可为名片选择已发布产品。推荐产品编号和顺序保存在名片草稿中，只有重新发布名片后才进入公开快照。因此修改推荐关系不会直接影响线上名片。

公开端按快照顺序展示推荐产品，同时再次过滤产品状态。产品下线、企业停用或素材变为不可公开时，公开接口不会返回对应内容。

## 权限与租户隔离

| 权限点 | 用途 |
| --- | --- |
| `product.read` | 查看本企业产品和分类 |
| `product.manage` | 新增、编辑、发布和下线本企业产品 |
| `material.read` | 查看本企业素材库 |
| `material.manage` | 上传、调整访问范围和删除本企业素材 |

所有企业接口从当前登录账户取得 `company_id`，不接受客户端指定租户。产品、分类和素材关联时会再次检查所属企业，跨租户编号统一按未找到处理。

## 主要接口

| 方法与路径 | 用途 |
| --- | --- |
| `GET/POST /api/v1/tenant/product-categories` | 查询或创建产品分类 |
| `PATCH /api/v1/tenant/product-categories/{id}` | 编辑、排序或停用分类 |
| `GET/POST /api/v1/tenant/products` | 分页查询或创建产品 |
| `GET/PATCH /api/v1/tenant/products/{id}` | 查看或编辑产品 |
| `POST /api/v1/tenant/products/{id}/status` | 发布或下线产品 |
| `GET/POST /api/v1/tenant/materials` | 查询或上传素材 |
| `PATCH /api/v1/tenant/materials/{id}/access` | 修改素材公开范围 |
| `DELETE /api/v1/tenant/materials/{id}` | 删除未被引用的素材 |
| `PUT /api/v1/tenant/cards/me/recommendations` | 更新本人名片推荐产品草稿 |
| `PUT /api/v1/tenant/cards/{employee_id}/recommendations` | 代管员工名片推荐产品 |
| `GET /api/v1/public/cards/{card_id}/products` | 获取名片公开推荐产品 |
| `GET /api/v1/public/products/{product_id}` | 获取已发布产品详情 |
| `GET /api/v1/public/materials/{material_id}` | 获取公开素材内容 |

## 验收覆盖

自动化测试覆盖无效文件不落库、私有素材不可公开访问、私有素材阻止产品发布、引用素材禁止删除、已发布产品禁止换用私有素材、产品下线后公开详情失效，以及推荐顺序仅在名片重新发布后生效。
