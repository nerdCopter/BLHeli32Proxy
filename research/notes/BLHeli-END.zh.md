<div class="container">

<div class="row">

<div class="col-lg-8 col-lg-offset-2 col-md-10 col-md-offset-1 post-container"
pagefind-body="">

## Foreword

前段时间刚参加完无人机展会，各种为战争服务的无人机，百花齐放，热闹程度远超前几年，没想到刚转头，无人机行业就又被打击了

## BLHeli被制裁

![image-20240604095924947](https://img.elmagnifico.tech/static/upload/elmagnifico/202406040959986.png)

简单说由于BLHeli广泛被无人机使用，搭载BLH的ESC并不能确定最终用途，所以整个BLH数据被禁止出口，包括BLH自身收款的银行都受到了影响，所以BLH停止开发和维护了。

- 实际上BLH是先停止，然后才发出来相关公告

![image-20240608014007781](https://img.elmagnifico.tech/static/upload/elmagnifico/202406080140878.png)

BLH大概在无人机市场里占90%，一个无人机就至少要搭载4个BLH电调，全世界大部分电调厂商都在国内，每年出货量大概几百上千万，BLH认可度之高，远超想象。

最初BLH大概是在2013年上线的，一上线就开源，其优异的性能和相对低廉的价格，一下就爆火了。而BLH初代还是8bit的单片机，成本低，性能也相对弱一些，随着时代的发展，16bit单片机本身发展不太好，被跳过去了，直接进入了32bit时代，BLH在初期估计是给各个制造商做技术支持，只是挣了点小钱。从2017年开始BLH进入32位时代，开始闭源，对应的所有new
features都加在了32位上，8位停止维护。

8位电调依然可以使用，而且很多低性能领域都可以用，每年依然有不小的出货量。对应的32位电调，BLH开始针对各个制造商，对激活BLH固件的电调开始收费，大概在1RMB左右。

BLH就算什么都不开发，每年估计也能躺赚几百万，而市面上的竞争对手，抱歉，基本没有，8位的强有力的竞争对手大概20年才有（JESC
BlueJay），32位的21年才有（AM32），闭源的选手有很多（SimonK，Kiss等），不过都不怎么火，而且他们的电调往往和自己的飞控要一起使用才能得到比较好的效果。

社区反应比我想象的要慢一点

> https://github.com/bitdump/BLHeli/issues/743

**由于服务器关闭了，很多人刚买的电调可能是有问题的版本，无法正常升级了**

![image-20240608015029387](https://img.elmagnifico.tech/static/upload/elmagnifico/202406080150415.png)、

作者表示他们还在获取许可中

### 破局

![image-20240608014614914](https://img.elmagnifico.tech/static/upload/elmagnifico/202406080146966.png)

BLH的认证模式是购买对应数量的Licenses，每激活一个电调会消耗一个，制造商都是前期一次性买n个，一次性支付n\*m美刀，而此次停止维护，是直接在制造商还未使用完Licenses的情况下，就停止了服务，有的制造商手上可能还有几十万次激活未被消耗。

与正式激活相对的，BLH也有测试版本，测试版本是只有100次上电工作的限制，使用完以后就无法使用了。想都不用想这种测试版，必然是在FLASH中写入了一个使用次数，而这个次数大概率是很容易逆向的。BLH主要是在BOOT阶段进行的校验和限制，所以要突破这一层，在这里做点手脚应该就行了，主要是针对固件的HACK（据说后来的测试版没有联网和次数限制，似乎可以长期使用）

BLH本身的上位机是Delphi写的，也没有做什么非常严格的加密或者保护，上位机这里也有突破口。

激活需要服务器，粗看了一下BLH用了https，所以这里要从接口上破解，需要先把https的接口给他逆向了，让他可以使用非https进行传输，然后直接抓包看接口请求是什么就行了。唯一的问题BLH的服务停了，不知道具体返回什么内容，需要结合上位机一起看回包内容。

这样劫持https就能做出来一个无感的上位替代版本

![image-20240603215033492](https://img.elmagnifico.tech/static/upload/elmagnifico/202406032150528.png)

国内制造商飞盈佳乐，直接打出一记，让我来开发，如果BLH作者敢头铁，直接把32位代码开源，那估计他人马上就没了

## 替代者

BLH32不开源，同时由于电调本身代码是汇编写的，基本就劝退了大部分人了，就算他开源了，也很少有人能修改，更别说适配其他MCU什么的了。

这次BLH停止维护，那么对应的开源社区的电调将迎来新生，比较有名的就是AM32和BlueJay

同样的AM32和BlueJay相对应用还是太少了，很多人对于他们的稳定性还是怀疑的，毕竟这是电调，出了一点问题就是坠机，BLH长达十一年的统治地位靠的就是稳定

### 上位替代：AM32

> https://github.com/am32-firmware/AM32

AM32相对还是比较小众的，支持的MCU比较少，但是有一部分电调是和BLH完全兼容的，但是当下阶段如果切换到AM32，那就再也不能切换回BLH了，你没有激活权限了

### 下位替代：BlueJay

> https://github.com/mathiasvr/bluejay

蓝鸟电调，他继承了BLH的8位电调，发扬光大，大部分32位电调的new
features都移植过来了

不过比起来，依然在某些性能上是不如BLH的

> https://github.com/bitdump/BLHeli/issues/744

## Summary

归根到底和俄乌战争脱不了干系，相信过不了几天老毛子就把他破了，更别说我看到这个消息发出来的人就叫`just hack it`

对于开源的AM32和BlueJay，如果形式愈演愈烈，可能他们也会被迫删库

制裁无人机没水平，直接制裁电调，这就让当前市场上给俄乌供货的制造商瞬间吃瘪，更别提其他正常使用的电调，DIY玩家用的电调，目前都被卡了不少货，这个事情已经发生一周了，今天才刚被曝出来，不知道国内其他几家做电调业务的现在打算怎么办。

## Quote

> https://github.com/bitdump/BLHeli/issues/743
>
> https://www.youtube.com/watch?v=GU0RoH_Pof0
>
> https://www.youtube.com/watch?v=\_PNuWXgYV74
>
> https://www.youtube.com/watch?v=AuBHXlWeUVc&ab_channel=JustHackIt
>
> https://www.facebook.com/share/p/tDjAETkfQXyj4kF4/
>
> https://oscarliang.com/am32-esc-firmware-an-open-source-alternative-to-blheli32/

------------------------------------------------------------------------

- <a href="/2024/05/30/Glyphica/" data-toggle="tooltip"
  data-placement="top"
  title="Glyphica: Typing Survival 短评">Previous<br />
  <span>Glyphica: Typing Survival 短评</span></a>
- <a href="/2024/06/09/AbioticFactor/" data-toggle="tooltip"
  data-placement="top" title="Abiotic Factor开服指南">Next<br />
  <span>Abiotic Factor开服指南</span></a>

<div class="comment">

<div id="disqus_thread" class="disqus-thread">

</div>

</div>

</div>

<div class="col-lg-2 col-lg-offset-0 visible-lg-block sidebar-container catalog-container">

<div class="side-catalog">

------------------------------------------------------------------------

##### <a href="#" class="catalog-toggle">CATALOG</a>

</div>

</div>

<div class="col-lg-8 col-lg-offset-2 col-md-10 col-md-offset-1 sidebar-container">

<div class="section">

------------------------------------------------------------------------

##### [FEATURED TAGS](/tags/)

<div class="tags">

<a href="/tags/#RaspberryPi" rel="9" title="RaspberryPi">RaspberryPi</a>
<a href="/tags/#嵌入式" rel="30" title="嵌入式">嵌入式</a>
<a href="/tags/#Git" rel="7" title="Git">Git</a>
<a href="/tags/#脚本" rel="2" title="脚本">脚本</a>
<a href="/tags/#python" rel="19" title="python">python</a>
<a href="/tags/#LeetCode" rel="30" title="LeetCode">LeetCode</a>
<a href="/tags/#C++" rel="10" title="C++">C++</a>
<a href="/tags/#APM" rel="2" title="APM">APM</a>
<a href="/tags/#FreeRTOS" rel="26" title="FreeRTOS">FreeRTOS</a>
<a href="/tags/#Markdown" rel="5" title="Markdown">Markdown</a>
<a href="/tags/#Embedded" rel="30" title="Embedded">Embedded</a>
<a href="/tags/#SD" rel="2" title="SD">SD</a>
<a href="/tags/#Linux" rel="2" title="Linux">Linux</a>
<a href="/tags/#Vim" rel="2" title="Vim">Vim</a>
<a href="/tags/#Ubuntu" rel="2" title="Ubuntu">Ubuntu</a>
<a href="/tags/#Tools" rel="8" title="Tools">Tools</a>
<a href="/tags/#STM32" rel="17" title="STM32">STM32</a>
<a href="/tags/#Maya" rel="22" title="Maya">Maya</a>
<a href="/tags/#LPWAN" rel="3" title="LPWAN">LPWAN</a>
<a href="/tags/#Graph%20Theory" rel="3" title="Graph Theory">Graph
Theory</a>
<a href="/tags/#Algorithm" rel="4" title="Algorithm">Algorithm</a>
<a href="/tags/#PathFind" rel="14" title="PathFind">PathFind</a>
<a href="/tags/#OMPL" rel="7" title="OMPL">OMPL</a>
<a href="/tags/#VPS" rel="33" title="VPS">VPS</a>
<a href="/tags/#QT" rel="3" title="QT">QT</a>
<a href="/tags/#Router" rel="2" title="Router">Router</a>
<a href="/tags/#JS" rel="2" title="JS">JS</a>
<a href="/tags/#Chrome" rel="2" title="Chrome">Chrome</a>
<a href="/tags/#Tampermonkey" rel="2"
title="Tampermonkey">Tampermonkey</a>
<a href="/tags/#API" rel="3" title="API">API</a>
<a href="/tags/#Java" rel="6" title="Java">Java</a>
<a href="/tags/#Spring" rel="2" title="Spring">Spring</a>
<a href="/tags/#MySql" rel="2" title="MySql">MySql</a>
<a href="/tags/#Springboot" rel="8" title="Springboot">Springboot</a>
<a href="/tags/#Docker" rel="3" title="Docker">Docker</a>
<a href="/tags/#V2ray" rel="5" title="V2ray">V2ray</a>
<a href="/tags/#TTRSS" rel="2" title="TTRSS">TTRSS</a>
<a href="/tags/#Nintendo%20Switch" rel="12"
title="Nintendo Switch">Nintendo Switch</a>
<a href="/tags/#Trace" rel="3" title="Trace">Trace</a>
<a href="/tags/#Crack" rel="11" title="Crack">Crack</a>
<a href="/tags/#BLHeli" rel="10" title="BLHeli">BLHeli</a>
<a href="/tags/#DSHOT" rel="2" title="DSHOT">DSHOT</a>
<a href="/tags/#ESC" rel="2" title="ESC">ESC</a>
<a href="/tags/#Music" rel="5" title="Music">Music</a>
<a href="/tags/#C#" rel="5" title="C#">C#</a>
<a href="/tags/#EasyCon" rel="8" title="EasyCon">EasyCon</a>
<a href="/tags/#Blog" rel="6" title="Blog">Blog</a>
<a href="/tags/#杂谈" rel="6" title="杂谈">杂谈</a>
<a href="/tags/#Proxy" rel="4" title="Proxy">Proxy</a>
<a href="/tags/#UAV" rel="3" title="UAV">UAV</a>
<a href="/tags/#GuinnessWorldRecords" rel="3"
title="GuinnessWorldRecords">GuinnessWorldRecords</a>
<a href="/tags/#NAS" rel="3" title="NAS">NAS</a>
<a href="/tags/#群晖" rel="3" title="群晖">群晖</a>
<a href="/tags/#ZeroTier" rel="3" title="ZeroTier">ZeroTier</a>
<a href="/tags/#Typora" rel="3" title="Typora">Typora</a>
<a href="/tags/#Map" rel="2" title="Map">Map</a>
<a href="/tags/#旅游" rel="15" title="旅游">旅游</a>
<a href="/tags/#Log" rel="2" title="Log">Log</a>
<a href="/tags/#JSON" rel="2" title="JSON">JSON</a>
<a href="/tags/#Cython" rel="2" title="Cython">Cython</a>
<a href="/tags/#Equip" rel="16" title="Equip">Equip</a>
<a href="/tags/#Goods" rel="8" title="Goods">Goods</a>
<a href="/tags/#Share" rel="5" title="Share">Share</a>
<a href="/tags/#DMX512" rel="2" title="DMX512">DMX512</a>
<a href="/tags/#Blender" rel="3" title="Blender">Blender</a>
<a href="/tags/#Game" rel="32" title="Game">Game</a>
<a href="/tags/#AP" rel="3" title="AP">AP</a>
<a href="/tags/#Network" rel="10" title="Network">Network</a>
<a href="/tags/#CloudFlare" rel="2" title="CloudFlare">CloudFlare</a>
<a href="/tags/#DIY" rel="5" title="DIY">DIY</a>
<a href="/tags/#WIFI" rel="2" title="WIFI">WIFI</a>
<a href="/tags/#Camera" rel="2" title="Camera">Camera</a>
<a href="/tags/#Life" rel="2" title="Life">Life</a>
<a href="/tags/#Diablo" rel="10" title="Diablo">Diablo</a>
<a href="/tags/#Sensor" rel="2" title="Sensor">Sensor</a>
<a href="/tags/#SES" rel="6" title="SES">SES</a>
<a href="/tags/#QQ" rel="3" title="QQ">QQ</a>
<a href="/tags/#Bot" rel="3" title="Bot">Bot</a>
<a href="/tags/#Python" rel="7" title="Python">Python</a>
<a href="/tags/#Vmq" rel="2" title="Vmq">Vmq</a>
<a href="/tags/#Jenkins" rel="4" title="Jenkins">Jenkins</a>
<a href="/tags/#米家" rel="8" title="米家">米家</a>
<a href="/tags/#ESP32" rel="6" title="ESP32">ESP32</a>
<a href="/tags/#Software" rel="5" title="Software">Software</a>
<a href="/tags/#C" rel="4" title="C">C</a>
<a href="/tags/#MT793x" rel="5" title="MT793x">MT793x</a>
<a href="/tags/#NXP" rel="4" title="NXP">NXP</a>
<a href="/tags/#CH32" rel="2" title="CH32">CH32</a>
<a href="/tags/#OpenWrt" rel="4" title="OpenWrt">OpenWrt</a>
<a href="/tags/#Onion" rel="2" title="Onion">Onion</a>
<a href="/tags/#Copilot" rel="2" title="Copilot">Copilot</a>
<a href="/tags/#Cursor" rel="6" title="Cursor">Cursor</a>
<a href="/tags/#Investment" rel="2" title="Investment">Investment</a>
<a href="/tags/#ChatGPT" rel="4" title="ChatGPT">ChatGPT</a>
<a href="/tags/#SFX" rel="2" title="SFX">SFX</a>
<a href="/tags/#Debug" rel="2" title="Debug">Debug</a>
<a href="/tags/#RouterOS" rel="5" title="RouterOS">RouterOS</a>
<a href="/tags/#Mikrotik" rel="5" title="Mikrotik">Mikrotik</a>
<a href="/tags/#GitLab" rel="2" title="GitLab">GitLab</a>
<a href="/tags/#Drone" rel="2" title="Drone">Drone</a>
<a href="/tags/#OpenAI" rel="4" title="OpenAI">OpenAI</a>
<a href="/tags/#VS%20Code" rel="4" title="VS Code">VS Code</a>
<a href="/tags/#管理" rel="6" title="管理">管理</a>
<a href="/tags/#build" rel="6" title="build">build</a>
<a href="/tags/#Kconfig" rel="5" title="Kconfig">Kconfig</a>
<a href="/tags/#CMake" rel="6" title="CMake">CMake</a>
<a href="/tags/#Su7%20Ultra" rel="14" title="Su7 Ultra">Su7 Ultra</a>
<a href="/tags/#Car" rel="14" title="Car">Car</a>
<a href="/tags/#AI" rel="19" title="AI">AI</a>
<a href="/tags/#MCP" rel="3" title="MCP">MCP</a>
<a href="/tags/#LLM" rel="2" title="LLM">LLM</a>
<a href="/tags/#Art" rel="3" title="Art">Art</a>
<a href="/tags/#审美" rel="3" title="审美">审美</a>
<a href="/tags/#Skills" rel="2" title="Skills">Skills</a>
<a href="/tags/#Agent" rel="7" title="Agent">Agent</a>

</div>

</div>

------------------------------------------------------------------------

##### FRIENDS

- [智伤帝](https://blog.l0v0.com/)
- [小静的博客](http://smilejing.cn/)
- [晨曦的博客](https://blog.whuzfb.cn/)
- [hiRipple](https://hiripple.com/)
- [草东日记](https://www.gaicas.com/)
- [MARKSZのBlog](https://molunerfinn.com/)
- [等你成为我的朋友](http://等你成为我的朋友)
- [Wait for you](http://Wait%20for%20you)

</div>

</div>

</div>
