# V0.4.0 员工管理说明

## 数据与权限边界

员工档案与登录账户是两个独立对象，通过可选的 `user_id` 关联。所有员工查询和修改都由服务端使用当前登录账户的 `company_id` 限定租户范围，客户端不能通过传入企业编号越权访问。

企业管理员默认拥有员工查看、创建、编辑、状态、导入、邀请和自助资料权限；其他企业角色默认仅拥有查看员工和维护本人资料权限，企业管理员可在角色权限页调整。

员工编号、手机号和邮箱在企业内分别唯一；不同企业可以使用相同值。员工编号保存前会去除首尾空格并转为大写，邮箱统一转为小写，手机号去除空格、括号和连字符。

## CSV 批量导入

调用 `POST /api/v1/tenant/employees/import`，请求体使用 UTF-8 CSV，`Content-Type` 为 `text/csv`。单次最多 500 行，必需列为 `employee_no,name`，可选列如下：

```csv
employee_no,name,phone,email,position,department_code,manager_employee_no,avatar_url,bio
E-001,张三,+8613800000000,zhangsan@example.com,销售经理,SALES,,https://example.com/avatar.jpg,负责华东区域
```

每一行独立校验和提交。错误行会返回 CSV 行号、错误代码和说明，正确行不会因其他行失败而回滚。直属上级必须已经存在，因此建议先导入管理者，再导入下属。

## 邀请与账户状态

企业管理员可为有邮箱且处于在职状态的员工生成邀请链接。系统只保存邀请令牌摘要，原始令牌只在接口响应中出现一次；链接默认 72 小时有效。对尚未激活的账户重新邀请时，旧链接立即失效。

员工通过邀请页设置符合强度要求的密码后才能登录。停用员工时，系统会停用关联账户、撤销已有会话并阻止再次登录；恢复员工时，只自动恢复由员工停用动作所停用的账户，不覆盖管理员独立执行的账户停用。

## 自助资料与公开策略

企业可从头像、手机号、邮箱和个人简介中配置员工允许自行维护的字段。本人接口不接受姓名、员工编号、部门、职位、直属上级、角色或账户关联字段。

离职员工的公开资料默认返回 404。企业也可以选择继续展示，并在响应中明确返回 `inactive` 状态。企业暂停时所有员工公开资料均不可访问。

## 主要接口

| 接口 | 用途 |
| --- | --- |
| `GET/POST /api/v1/tenant/employees` | 查询或新增员工 |
| `GET/PATCH /api/v1/tenant/employees/{id}` | 查看或编辑员工 |
| `POST /api/v1/tenant/employees/{id}/status` | 停用或恢复员工 |
| `POST /api/v1/tenant/employees/import` | CSV 批量导入 |
| `POST /api/v1/tenant/employees/{id}/invite` | 生成或重新生成邀请 |
| `GET/PATCH /api/v1/tenant/employees/me` | 查看或维护本人资料 |
| `POST /api/v1/auth/invitations/accept` | 接受邀请并设置密码 |
| `GET /api/v1/public/employees/{id}` | 查询允许公开的员工资料 |
