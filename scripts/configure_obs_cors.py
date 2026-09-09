"""一次性脚本:为 obs-mushroom 桶配置 CORS,允许浏览器跨域 PUT/POST/GET。

参考:https://support.huaweicloud.com/usermanual-obs/zh-cn_topic_0066036542.html
"""
import sys

from obs import CorsRule, ObsClient


def main() -> None:
    c = ObsClient(
        access_key_id="E4PODEJ2KFRXLIBACJG5",
        secret_access_key="4G3TvKp0ehqOQPcDPOavWxiCgbid7fAGVxbjUMl5",
        server="obs.cn-central-221.ovaijisuan.com",
    )

    # 规则:允许从任意 http/https 来源
    # 允许方法:GET/POST/PUT/DELETE/HEAD(覆盖直传需要的 PUT)
    # 允许头:x-amz-*  +  Content-Type  +  Authorization
    # 暴露头: ETag(直传需要回读 ETag)
    rules = [
        CorsRule(
            id="pixelhoard-web-upload",
            allowedOrigin=["*"],
            allowedMethod=["GET", "POST", "PUT", "DELETE", "HEAD"],
            allowedHeader=["*"],
            exposeHeader=["ETag", "x-amz-request-id"],
            maxAgeSecond=3600,  # 注意:SDK 参数名是单数
        ),
    ]
    resp = c.setBucketCors("obs-mushroom", rules)
    if resp.status < 300:
        print(f"✓ CORS 规则已设置到 obs-mushroom (status={resp.status})")
    else:
        print(f"✗ 失败: {resp.errorCode} - {resp.errorMessage}")
        sys.exit(1)

    # 验证(注意:resp.body 直接是 list,不是嵌套对象)
    resp2 = c.getBucketCors("obs-mushroom")
    print(f"  验证 getBucketCors: status={resp2.status}")
    if resp2.body:
        print(f"  当前规则数: {len(resp2.body)}")
        for r in resp2.body:
            print(
                f"    - id={r.id} origin={r.allowedOrigin} method={r.allowedMethod}"
            )


if __name__ == "__main__":
    main()