<div class="container">

<div class="row">

<div class="col-lg-8 col-lg-offset-2 col-md-10 col-md-offset-1 post-container"
pagefind-body="">

## Foreword

最近要用DSHOT，然后就发现一堆问题，首先是DSHOT没有那种特别详细的介绍手册，基本全靠几个帖子和博客的内容，剩下的就是代码里内容，很多地方也没说清楚到底怎么弄。

## DSHOT历史

首先随着时间的发展，DSHOT也越来越强了，目前来看应该是最强ESC协议了

平常ESC多数用的都是PWM，但是传统PWM也有问题，比如50HZ，那很明显，我控制频率可以达到400HZ的话，实际输出的控制信号却只有50HZ，那相当于剩下的频率都浪费了，对于反馈而言也不及时，所以这给整个控制系统带来了极大的延迟，首先是把pwm的频率提升到和控制输出频率相同的程度，那么就可以和控制信号兼容了，当然那会pwm基本已经可以输出400HZ，甚至更高。但是除了四轴，还有其他的各种模型可能也需要更高的输出频率，那么这个时候PWM就不够了。

后来就有了Oneshot，Multishot等等，不过最开始的是DSHOT150，然后DSHOT300，DSHOT600，现在的DSHOT1200。在这之前最强的应该是Multishot，当然对应协议的提升，也要求电调的控制板更强，从之前的8位，16位，到现在的32位单片机，并且时钟频率也从8Mhz，一直提升到了现在的48Mhz，72Mhz甚至更高。

![](https://img.elmagnifico.tech/static/upload/elmagnifico/SrPBVdNHDGEhiec.png)

这些都是老图了，可以看到DSHOT600已经非常接近Multishot了，而DSHOT1200直接碾压

DSHOT将模拟信息作为数字信号来处理，自然就让电调也进一步，平常电调都需要校准油门行程，而DSHOT理论上可以不需要每次重新校准油门行程（实际上DSHOT也需要校准的，不过那不是我们做的）

#### DSHOT评价

简单说，好处是抗干扰，不用校准，随时切换正反转，可以拿到电调反馈信息，半有感，响应快，延迟低。

不方便的地方：对于主控的要求高，可能要多一根线，电调成本增高（需要增加电流相关芯片）

#### DSHOT支持

最初DSHOT是kiss飞控的电调开发者提出来的，后来大家广泛支持了DSHOT协议，由于BLHli使用的最广，后续大部分BLH32的电调都支持了。后续kiss还基于DSHOT开发一些私有的command，这一部分没有被BLH接受，所以存在两部分不同的DSHOT版本，Betafly的代码中可以看到类似的区分

## DSHOT协议

DSHOT协议本身将原本的模拟信号转变成了数字信号，并且加入了校验位，其单loop时间足够快，分辨率高，有校验，同时还有telemetry作为反馈。

DSHOT本身一个完整控制帧，是16bits，其中11bits用来表示油门，1bit表示telemetry，4bits表示crc校验

| bit      | 11bits | 1bit | 4bits |
|----------|--------|------|-------|
| 表示范围 | 0-2047 | 0-1  | 0-15  |

- 0，用于电调解锁，1-47是给telemetry用的

- 1-5，电调鸣叫，低频-\>高频

- 6，ESC 版本信息或者是序列号，通过telemetry返回

- 7，8是对应两个旋转方向，做双向控制使用的

- 9，10，3d模式开关，9关，10开

- 11，获取esc 配置

- 12，保存esc 配置

- 13，telemetry扩展信息打开，就是反馈温度、电压、电流

- 14，扩展信息关闭

- 20，21也是切换自选方向，不知道和7，8有什么区别

- 22-29，3个LED的亮灭控制

- 30，音频流传输开关，仅限kiss电调

- 31，静音模式开关，仅限kiss电调

- 48到2047则是对应真实的油门0-1999，这样油门就有2000的分辨率，大部分情况下应该说够用了。

然后后面的4bits
crc校验可以防止给出错误帧导致电调给出错误的控制信号（实际电调内部还有一个根据输入，转换到PID电机输出的东西）

![](https://img.elmagnifico.tech/static/upload/elmagnifico/QVknPb7qy6Guplc.png)

既然是数字信号，那么对于0和1的定义就是必须要有的，其实这里0和1是按照占空比来区分的。75%左右的占空比就是1，37.5%左右的占空比就是0.

如下图所示。

![](https://img.elmagnifico.tech/static/upload/elmagnifico/sLR62aojHtD1ybr.png)

这样原本的模拟信号就组测了一个个数字bit，从而形成一个完整信号帧，这里的75%要求不是很严格，稍微多一些少一些都能正常识别

![](https://img.elmagnifico.tech/static/upload/elmagnifico/9s6PV5e1pbEzSO3.png)

而有了上面的基础协议以后，DSHOT剩下的就是规定实际每个bit的时间
，就可以决定输出的频率等信息了。

| 模式       | 比特率      | 输出频率 | 单bit时间 | 1的高电平时间 | 0的高电平时间 |
|------------|-------------|----------|-----------|---------------|---------------|
| Dshot 150  | 150 Kbit/s  | 4.05 kHz | 6.67 µs   | 5.00 µs       | 2.50 µs       |
| Dshot 300  | 300 Kbit/s  | 8.09 kHz | 3.33 µs   | 2.50 µs       | 1.25 µs       |
| Dshot 600  | 600 Kbit/s  | 16.0 kHz | 1.67 µs   | 1.25 µs       | 0.625 µs      |
| Dshot 1200 | 1200 Kbit/s | 32.0 kHz | 0.83 µs   | 0.625 µs      | 0.313 µs      |

（这里的输出频率仅供参考，实际可能比这个略高或者略低都可以正常工作）

这个图里的单bit时间和0，1的表示都是按照，1，0.75，0.375来表示的，而理论频率其实可以根据bit时间来反算，比如Dshot
600时，实际输出一个loop需要80/3
us，可以得到理论频率大概是37.5khz，这个频率就已经非常高了，但是实际上并不可以。实际使用的时候，每帧之间需要一个间隔时间，用来区分2帧。而DSHOT600,官方没有给明确的时间，多数人都是从某个帖子里看到的要给的时间是2us左右。

这里我说明一下，实际并不是2us，应该是3个bit时间，取决于使用的模式，DSHOT1200可能需要更多一点4bit时间，这个都是我实际测试的结果（有可能受到电调和电机的实际情况影响，需要自行测试）。多个开源飞控里的我看到都是至少3bit时间，如果少于3bit时间，输出相同的油门，可以看到电机明显的顿挫，而时间给够以后明显流畅了。实际输出的频率自然也会随着这3bit降低，大概就变成了31.5khz，我实测是ok的。

2023.4.10，其实Dshot协议已经不再限制速率了，基本上只要你的协议是正确的，任何速度的Dshot都可以被正确识别并工作。目前上限速度是
Dshot 2400，超过这个可能识别不了

#### CRC

既然这里有CRC，然后无论哪里都不具体说用的是啥CRC,下面是实际4位crc的算法，packet中是只有油门的，没有telemetry，可能需要根据情况设置telemetry

<div class="language-c highlighter-rouge">

<div class="highlight">

``` highlight
uint16_t add_checksum_and_telemetry(uint16_t packet) {
    uint16_t packet_telemetry = (packet << 1) | 0;
    uint8_t i;
    int csum = 0;
    int csum_data = packet_telemetry;

    for (i = 0; i < 3; i++) {
        csum ^=  csum_data;   // xor data by nibbles
        csum_data >>= 4;
    }
    csum &= 0xf;
    packet_telemetry = (packet_telemetry << 4) | csum;

    return packet_telemetry;    //append checksum
}
```

</div>

</div>

#### 解锁

一般支持DSHOT的都是BLH的电调了，然后DSHOT解锁比较特殊，和平常的PWM直接给输出就转不一样。

DSHOT必须先给0，持续3s，不是0油门，而是全bit=0，对电调进行解锁以后才能开始运转

平常的PWM是必须先给0解锁，保持一会就可以随意加油门了

切换了输出协议也要这样来一下，比如PWM切换到DSHOT或者OneSHOT切换到DSHOT，都要重新做一次解锁

#### telemetry

有一些电调支持返回当前电调和电机的信息，比如温度、电压、电流、累计电流总量、转速等信息。

相当于是在没有编码器的情况，让这个电机成为半有感电机了，由于这些信息本质上是来自于电调，所以有可能是不准确的，甚至发生短路或者某些特定异常的时候电调不一定能检测出来。

要使用telmetry，还需要电调支持一个输出接口，这个接口也使用相同的dshot协议进行数据传输。只有在输出的dshot里置位了telemetry，才会有信息返回。

同时电调的设置里也要开启回应telmetry才行

![](https://img.elmagnifico.tech/static/upload/elmagnifico/D3rMEyWJnj7kpbR.png)

有了这些基础，DSHOT基本就可以正常工作了

DSHOT的telemtry的具体含义定义得去源码里参考，这里我没有使用，暂时给不了

## STM32 HAL DMA PWM 输出bug

实际使用DSHOT的时候就会发现一点小问题，由于DSHOT可以输出的频率非常高，而要每时每刻去变timer中的ccr显然不能单线程死循环跑，太影响性能了。这里就要用DMA来实现自动喂CCR寄存器。

这里做设计就要注意一下，ST的DMA是有限的，并且有的通道可能只有一个选择，不能切到其他DMA或者换通道，而且DMA是一对一的，不能相同通道相同流同时使用，这就要提前规避，不然最后DSHOT输出不了。

DMA
timer的例程，官方就有好多个，但是都是单通道输出，如果只是单通道肯定也没啥问题，但我这里要用的是4通道，并且是用HAL库的函数来做的，然后我就发现貌似同一时刻只有一个通道工作

这个是普通PWM开始输出的函数，可以看到没啥大问题

<div class="language-c highlighter-rouge">

<div class="highlight">

``` highlight
HAL_StatusTypeDef HAL_TIM_PWM_Start(TIM_HandleTypeDef *htim, uint32_t Channel)
{
  /* Check the parameters */
  assert_param(IS_TIM_CCX_INSTANCE(htim->Instance, Channel));

  /* Enable the Capture compare channel */
  TIM_CCxChannelCmd(htim->Instance, Channel, TIM_CCx_ENABLE);
  
  if(IS_TIM_ADVANCED_INSTANCE(htim->Instance) != RESET)  
  {
    /* Enable the main output */
    __HAL_TIM_MOE_ENABLE(htim);
  }
    
  /* Enable the Peripheral */
  __HAL_TIM_ENABLE(htim);
  
  /* Return function status */
  return HAL_OK;
} 
```

</div>

</div>

这里是对应的DMA的PWM输出方式，DMA
PWM开始工作的要求是timer必须是ready状态的，而实际上只要开了一个通道，就会导致他将timer状态修改成busy，然后其他通道全都用不了。

无论DMA输出模式是normal还是circle模式，都会被这个busy给强制退出

<div class="language-c highlighter-rouge">

<div class="highlight">

``` highlight
HAL_StatusTypeDef HAL_TIM_PWM_Start_DMA(TIM_HandleTypeDef *htim, uint32_t Channel, uint32_t *pData, uint16_t Length)
{
  /* Check the parameters */
  assert_param(IS_TIM_CCX_INSTANCE(htim->Instance, Channel));
  
  if((htim->State == HAL_TIM_STATE_BUSY))
  {
     return HAL_BUSY;
  }
  else if((htim->State == HAL_TIM_STATE_READY))
  {
    if(((uint32_t)pData == 0 ) && (Length > 0)) 
    {
      return HAL_ERROR;                                    
    }
    else
    {
      /*
       * DMA work in circle mode
       * there is a bug that PWM start DMA will lock the timer
       * just one channel work other blocked
       * you could remove the code or add a state at the end
       * so here i add a HAL_TIM_STATE_READY state at the end
       * */
      htim->State = HAL_TIM_STATE_BUSY;
    }
  }    
  switch (Channel)
  {
    case TIM_CHANNEL_1:
    {      
      /* Set the DMA Period elapsed callback */
      htim->hdma[TIM_DMA_ID_CC1]->XferCpltCallback = HAL_TIM_DMADelayPulseCplt;
     
      /* Set the DMA error callback */
      htim->hdma[TIM_DMA_ID_CC1]->XferErrorCallback = HAL_TIM_DMAError ;
      
      /* Enable the DMA Stream */
      HAL_DMA_Start_IT(htim->hdma[TIM_DMA_ID_CC1], (uint32_t)pData, (uint32_t)&htim->Instance->CCR1, Length);
      
      /* Enable the TIM Capture/Compare 1 DMA request */
      __HAL_TIM_ENABLE_DMA(htim, TIM_DMA_CC1);
    }
    break;
    
    case TIM_CHANNEL_2:
    {
      /* Set the DMA Period elapsed callback */
      htim->hdma[TIM_DMA_ID_CC2]->XferCpltCallback = HAL_TIM_DMADelayPulseCplt;
     
      /* Set the DMA error callback */
      htim->hdma[TIM_DMA_ID_CC2]->XferErrorCallback = HAL_TIM_DMAError ;
      
      /* Enable the DMA Stream */
      HAL_DMA_Start_IT(htim->hdma[TIM_DMA_ID_CC2], (uint32_t)pData, (uint32_t)&htim->Instance->CCR2, Length);
      
      /* Enable the TIM Capture/Compare 2 DMA request */
      __HAL_TIM_ENABLE_DMA(htim, TIM_DMA_CC2);
    }
    break;
    
    case TIM_CHANNEL_3:
    {
      /* Set the DMA Period elapsed callback */
      htim->hdma[TIM_DMA_ID_CC3]->XferCpltCallback = HAL_TIM_DMADelayPulseCplt;
     
      /* Set the DMA error callback */
      htim->hdma[TIM_DMA_ID_CC3]->XferErrorCallback = HAL_TIM_DMAError ;
      
      /* Enable the DMA Stream */
      HAL_DMA_Start_IT(htim->hdma[TIM_DMA_ID_CC3], (uint32_t)pData, (uint32_t)&htim->Instance->CCR3,Length);
      
      /* Enable the TIM Output Capture/Compare 3 request */
      __HAL_TIM_ENABLE_DMA(htim, TIM_DMA_CC3);
    }
    break;
    
    case TIM_CHANNEL_4:
    {
     /* Set the DMA Period elapsed callback */
      htim->hdma[TIM_DMA_ID_CC4]->XferCpltCallback = HAL_TIM_DMADelayPulseCplt;
     
      /* Set the DMA error callback */
      htim->hdma[TIM_DMA_ID_CC4]->XferErrorCallback = HAL_TIM_DMAError ;
      
      /* Enable the DMA Stream */
      HAL_DMA_Start_IT(htim->hdma[TIM_DMA_ID_CC4], (uint32_t)pData, (uint32_t)&htim->Instance->CCR4, Length);
      
      /* Enable the TIM Capture/Compare 4 DMA request */
      __HAL_TIM_ENABLE_DMA(htim, TIM_DMA_CC4);
    }
    break;
    
    default:
    break;
  }

  /* Enable the Capture compare channel */
  TIM_CCxChannelCmd(htim->Instance, Channel, TIM_CCx_ENABLE);
    
  if(IS_TIM_ADVANCED_INSTANCE(htim->Instance) != RESET)  
  {
    /* Enable the main output */
    __HAL_TIM_MOE_ENABLE(htim);
  }
  
  /* Enable the Peripheral */
  __HAL_TIM_ENABLE(htim); 

  /*
     * DMA work in circle mode
     * there is a bug that PWM start DMA will lock the timer
     * just one channel work other blocked
     * you could remove the code or add a state at the end
     * so here i add a HAL_TIM_STATE_READY state at the end
     * */
  htim->State = HAL_TIM_STATE_READY;

  /* Return function status */
  return HAL_OK;
}
```

</div>

</div>

这个busy状态直到DMA传输完成才会返回并且切换，这就导致这几路PWM无法同时输出

<div class="language-c highlighter-rouge">

<div class="highlight">

``` highlight
/**
  * @brief  TIM DMA Period Elapse complete callback. 
  * @param  hdma: pointer to a DMA_HandleTypeDef structure that contains
  *                the configuration information for the specified DMA module.
  * @retval None
  */
static void TIM_DMAPeriodElapsedCplt(DMA_HandleTypeDef *hdma)
{
  TIM_HandleTypeDef* htim = ( TIM_HandleTypeDef* )((DMA_HandleTypeDef* )hdma)->Parent;
  
  htim->State= HAL_TIM_STATE_READY;
  
  HAL_TIM_PeriodElapsedCallback(htim);
}
```

</div>

</div>

基于这个原因，我就在前面的函数退出前直接加了一个htim-\>State =
HAL_TIM_STATE_READY，强制让timer此时可以正常工作。

## DMA PWM输出第一个bit bug

这里讨论的不再是DSHOT了，而是单纯这个DMA输出PWM，在启动的一瞬间会出现2个0的情况，这个情况目前我解不了，应该是DMA的bug。

我之前是想直接用DMA
PWM来模拟一个串口，直接输出串口信号，实际上我成功了，可以正常被识别。

但是这里会遇到一个问题，就是DMA首次输出的时候会出错，我是用circle模式，如果是normal模式的话，每次调用start的时候都会出错。

正常串口协议是这样的：

![](https://img.elmagnifico.tech/static/upload/elmagnifico/1CeRZVjT362nEmD.png)

姑且不论后面的0-7位是0还是1，而我实际从示波器上看到的是这样的：

![](https://img.elmagnifico.tech/static/upload/elmagnifico/2i5wDnvR64pEJtI.png)

也就是第一个起始位0，被输出了2个0，如果是circle模式，后面无论输出多少个0或者起始位，都不会再出现这个问题。

只要重新开启DMA或者重新激活PWM输出，那么输出的第一个bit就一定会出现这个问题。

正常来说输出0的时候，就是ccr为0，period的值如果为1000，然后输出就是0了，要避免第一bit出错，那么还有个办法，就是原本的0不用0，而是用1，这样识别起来还是0，虽然从示波器上会看到每个0前面有一个小毛刺，而如果要输出的是其他任何不为0的值，那么一定不会出错，只有第一次输出0的时候出错。

这个问题无论怎么调整DMA或者timer的极性或者其他设置都没用，只会让第一个出错的变成2个1或者2个0，肯定会出错，只要DMA一启动这个错误的bit就会出现。

## DMA PWM输出切换延迟

我实际想要实现的是单线DMA
PWM模拟串口输入和输出，输出没有大问题，但是模拟输入的时候就有明显问题了，从DMA
PWM输出模式切换到普通IO的模式的过程花费的时间超过了52us，导致实际使用19200波特率的情况下，单线串口输入的时候，信号丢失了。

某种程度上说目前的HAL库还是太重型了，虽然带来了一部分好处，比如统一配置，统一回调，更多的东西变成了一种约定（类似于springboot），你知道你就能正常用，你不知道你就用的很奇怪。好处是HAL的代码至少写的比你健壮一些，但是坏处就是有很多冗余性的东西，导致了现在的性能问题，甚至有的HAL内部问题，如果不仔细看底层实现是发现不了的。

## End

除了上面这个错以外，其实还有DMA帧错误，实际上帧错误是使用FIFO才会出现的，而FIFO是disable的，但是初始化以后还是默认开启了帧错误中断，这就是很多人明明没用FIFO但是却在DMA完成回调时看到了帧错误的错误回调，而这个问题貌似也已经好多年了都没修复，不知道为什么

而我看到了chibiOS等系统直接将板级资源重新定义，然后自己实现一个hal库，剩下的就是根据硬件去实现对应的hal库这种方式感觉更集中一些，在应用层屏蔽底层更完全一些，而且可以调用的系统资源也相对更完整一些。

## Quote

> https://www.youtube.com/watch?v=EQJgh-o-uHo
>
> https://github.com/betaflight/betaflight/wiki/DSHOT-ESC-Protocol
>
> https://dmrlawson.co.uk/index.php/2017/12/04/dshot-in-the-dark/
>
> https://www.rcgroups.com/forums/showthread.php?2756129-Dshot-testing-a-new-digital-parallel-ESC-throttle-signal
>
> https://blog.seidel-philipp.de/dshot-digital-esc-signal/
>
> https://www.speedgoat.com/help/slrt/page/io_main/refentry_dshot_usage_notes
>
> https://blck.mn/2016/11/dshot-the-new-kid-on-the-block/
>
> http://kiss.flyduino.net/dshot-new-digital-protocol-for-kiss/
>
> https://github.com/bitdump/BLHeli/issues/234

------------------------------------------------------------------------

- <a href="/2020/06/03/BLHeli-Uart-Usb-Protocol/" data-toggle="tooltip"
  data-placement="top" title="BLHeli-Uart-Usb-Protocol">Previous<br />
  <span>BLHeli-Uart-Usb-Protocol</span></a>
- <a href="/2020/06/07/V2ray-WS-TLS/" data-toggle="tooltip"
  data-placement="top" title="V2ray WS TLS自动续签证书+订阅">Next<br />
  <span>V2ray WS TLS自动续签证书+订阅</span></a>

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
