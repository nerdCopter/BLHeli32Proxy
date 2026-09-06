<div class="container">

<div class="row">

<div class="col-lg-8 col-lg-offset-2 col-md-10 col-md-offset-1 post-container"
pagefind-body="">

## Foreword

万万没想到BLH竟然还有后续，这次遇到了一个算是恶性bug吧。

## BUG

由于需要在ESC上电时进行配置检测，如果不对需要重新设置ESC。而之前使用的版本都是100%没问题的，基本不会出现校准失败的情况。而新版发现了异常，每次上电后第一次通信，必然在连接阶段出现错误。现象就是发送连接信息以后

<div class="language-plaintext highlighter-rouge">

<div class="highlight">

``` highlight
00 00 00 00 00 00 00 00 00 00 00 00 0D 42 4C 48 65 6C 69 F4 7D
```

</div>

</div>

正常情况下应该回复如下内容

<div class="language-plaintext highlighter-rouge">

<div class="highlight">

``` highlight
34 37 31 6C 15 06 07 04 30 
```

</div>

</div>

但是实际上只要我发送了，必然超时
。由于是单根通信，所以当我发送完以后，立马切换到接收模式等待串口下降沿，而实际上一直等到超时，都等不到后续的下降沿。

## Debug

先是怀疑我自己接收有问题，错过了，下降沿。反复debug了好几次，各种打印时间，发现实际上肯定没有错误，就是没收到下降沿。

然后既然接收没问题，怀疑我发送有问题，单独接线出来，发现直接读串口完全没问题，数据也正确。说明发送也没问题。好家伙，那只能怀疑硬件有问题了，老硬件跑相同代码，确实不会出现这个奇葩问题，每次100%通过。对比半天，硬件连接上也没啥明显问题。

那只好拿逻辑分析仪看一下具体是啥情况了。

![](https://img.elmagnifico.tech/static/upload/elmagnifico/er3qT6aK5Az9JNO.png)

然后就看到了，当7D发完，就看到有一个下拉信号，然后显示了一次帧错误。但是在此以后，电调一直没有回复。

再看后面一次正常的操作，发现这里依然存在一个下拉信息，还是一样的帧错误，但是电调有回复了，后续流程都是正常的了。

![](https://img.elmagnifico.tech/static/upload/elmagnifico/hr5MPoYbG49aDcC.png)

仔细看了一下这个下拉是我写的，然后去掉了，但是该不回复还是不回复，和我拉不拉没关系。

当我把这个下拉去掉以后，帧错误就消失了。

而第二次必然正确，所以怀疑是电调的初始化状态机有问题，每次都要我试错，让他的状态机跑到正确的时候才能，正确读写。

## 临时解

BLH新版本电调的串口配置timeout目前看都在5s左右，一旦你连接失败了，都必须等5s再发送才能有反应，否则会一直没回应。而以前的版本完全没有超时时间这个概念，失败了，立马重发也能得到响应。

由于校准时是顺序执行，所以快不的，4个电调，让他失败一次就是20多秒过去了，启动时间就拖得太长了。

而电调本身启动大概需要4s左右，这4s内传输大概率都是失败的。这样一次校准下来就接近30s了。

由于这个状态机的错误，要绕过，只好提前将每个esc进行一次connect，然后直接disconnect，完全无视他是否成功。

然后下一轮循环再进行实际的connect和check。这样操作以后，大概校准一轮需要10s左右，目前只能做到这种程度了。

## Summary

BLH的31.80以后的版本貌似都有这个问题，暂时没得解。

------------------------------------------------------------------------

- <a href="/2021/11/08/Mysql-binglog-recover/" data-toggle="tooltip"
  data-placement="top" title="Mysql binlog 数据恢复">Previous<br />
  <span>Mysql binlog 数据恢复</span></a>
- <a href="/2021/12/14/Diablo-kdc-failed/" data-toggle="tooltip"
  data-placement="top"
  title="暗黑2重制版Kill Diablo Clone 日记">Next<br />
  <span>暗黑2重制版Kill Diablo Clone 日记</span></a>

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
