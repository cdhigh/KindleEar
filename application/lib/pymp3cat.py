#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#合并mp3文件
#来源：https://github.com/dmulholl/mp3cat
#将go语言转换为python，方便类似GAE这样不能执行二进制文件的平台合并mp3
import os, io, struct

#版本
MPEGVersion2_5 = 0
MPEGVersionReserved = 1
MPEGVersion2 = 2
MPEGVersion1 = 3
#层
MPEGLayerReserved = 0
MPEGLayerIII = 1
MPEGLayerII = 2
MPEGLayerI = 3
#声道模式
Stereo = 0
JointStereo = 1
DualChannel = 2
Mono = 3

#位率对应表
v1_br = {
    3: (0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448), #layer1
    2: (0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384), #layer2
    1: (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320), #layer3
}

v2_br = {
    3: (0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256),
    2: (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160),
    1: (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160),
}

#采样率对应表[ver][layer]
samplingTable = ((11025, 12000, 8000), (0, 0, 0), (22050, 24000, 16000), (44100, 48000, 32000))

#每帧的采样数对应表[ver][layer]
sampleCountTable = ((0, 576, 1152, 384), (0, 0, 0, 0), (0, 576, 1152, 384), (0, 1152, 1152, 384))

#通道信息SideInfo大小，相对于帧头偏移
def GetSideInfoSize(frame):
    size = 0
    if frame['layer'] == MPEGLayerIII:
        if frame['mpegVer'] == MPEGVersion1:
            size = 21 if frame['channelMode'] == Mono else 36
        else:
            size = 13 if frame['channelMode'] == Mono else 21
    return size

#判断一个音乐帧是否是VBR帧头
def IsVBRHeader(frame):
    infoSize = GetSideInfoSize(frame)
    if frame['len'] < 4 + infoSize:
        return False

    flag = frame['raw'][infoSize:infoSize+4]
    if (flag == b'Xing') or (flag == b'Info'):
        return True
    #再判断是否是VBRI头，固定偏移36字节
    elif (frame['len'] > 4 + 36) and (frame['raw'][36:36+4] == b'VBRI'):
        return True
    
    return False

#获取流对象里面的下一个对象帧，可能为TAG/ID3/FRAME
#stream: 流对象
def NextObject(stream):
    while True:
        start = stream.tell()
        header1 = stream.read(4)
        if len(header1) != 4:
            return None

        #ID3v1标识: 'TAG'，包括标签头在内，一共128字节
        if header1[0:3] == b'TAG':
            stream.seek(start + 128)
            return {'type': 'TAG', 'start': start, 'end': stream.tell(), 'len': 128}
        elif header1[0:3] == b'ID3':
            #ID3V2头一共10个字节
            #char Header[3]; #ID3
            #char Ver; #版本号ID3V2.3 就记录3
            #char Revision; #副版本号此版本记录为0
            #char Flag; #标志字节，只使用高三位，其它位为0
            #char Size[4]; #标签大小，不包含标签头的10个字节
            #标签大小共四个字节，每个字节只使用低7位，最高位恒为0，计算时将最高位去掉，得到28bit的数据
            header2 = stream.read(6)
            if len(header2) != 6:
                return None
            length = ((header2[2] & 0x7f) * 0x200000 + (header2[3] & 0x7f) * 0x400
                    +(header2[4] & 0x7f) * 0x80 + (header2[5] & 0x7f))
            
            stream.seek(start)
            frame = {'type': 'ID3', 'len': length}
            frame['start'] = start
            frame['raw'] = stream.read(length + 10) #长度不包含头部10个字节
            frame['end'] = stream.tell()
            return frame
        elif (header1[0] == 0xff) and ((header1[1] & 0xe0) == 0xe0): #11比特的1，一个音乐数据帧开始
            frame = ParseMusicHeader(header1)
            if frame:
                stream.seek(start)
                frame['start'] = start
                frame['raw'] = stream.read(frame['len']) #帧长度包含头部4个字节
                frame['end'] = stream.tell()
                return frame

        #出错，往后跳一个字节再重新尝试
        stream.seek(start + 1)

#只返回有效音乐帧的生成器
def IterFrame(stream):
    while True:
        obj = NextObject(stream)
        type_ = obj['type'] if obj else ''
        if type_ == 'FRAME':
            yield obj
        elif type_ not in ('TAG', 'ID3'):
            return

#返回输入流的ID3V2标签帧
def FindID3v2Tag(stream):
    while True:
        obj = NextObject(stream)
        type_ = obj['type'] if obj else ''
        if type_ == 'ID3':
            return obj
        elif type_ not in ('TAG', 'FRAME'):
            return None

#校验音乐数据帧头是否合法，header一共四个字节
#校验正确返回帧头字典，否则返回None
# typedef FrameHeader
# {
# unsigned int sync:11;                 //同步信息
# unsigned int version:2;               //版本
# unsigned int layer: 2;                //层
# unsigned int error protection:1;      //CRC校验
# unsigned int bitrate_index:4;         //位率
# unsigned int sampling_frequency:2;    //采样频率
# unsigned int padding:1;               //帧长调节
# unsigned int private:1;               //保留字
# unsigned int mode:2;                  //声道模式
# unsigned int mode extension:2;        //扩充模式
# unsigned int copyright:1;             //版权
# unsigned int original:1;              //原版标志
# unsigned int emphasis:2;              //强调模式
# }HEADER, *LPHEADER;
def ParseMusicHeader(header):
    mpegVer = (header[1] & 0x18) >> 3 #2位，0-MPEG2.5，1-未使用，2-MPEG2，3-MPEG1
    if mpegVer == MPEGVersionReserved:
        return None
    layer = (header[1] & 0x06) >> 1 #2位，层, 0-未使用，1-Layer3, 2-Layer2, 3-Layer3
    if layer == 0:
        return None
    crcProt = (header[1] & 0x01) == 0x00 #是否有CRC校验，0-校验
    bitRateIndex = (header[2] & 0xf0) >> 4 #位率索引，共4位
    if bitRateIndex == 0 or bitRateIndex == 15:
        return None
    
    #查表得出位率
    if mpegVer == MPEGVersion1:
        bitRate = v1_br.get(layer)[bitRateIndex] * 1000
    else:
        bitRate = v2_br.get(layer)[bitRateIndex] * 1000

    samplingRateIndex = (header[2] & 0x0c) >> 2 #采样率索引，2位
    if samplingRateIndex == 3:
        return None
    
    #查表得出采样率
    samplingRate = samplingTable[mpegVer][samplingRateIndex]
    
    paddingBit = (header[2] & 0x02) == 0x02 #帧长调节 (1 bit)
    privateBit = (header[2] & 0x01) == 0x01 #保留字 (1 bit)
    channelMode = (header[3] & 0xc0) >> 6 #声道模式 (2 bits)
    modeExtension = (header[3] & 0x30) >> 4 #扩充模式，仅用于 Joint Stereo mode. (2 bits)
    if (channelMode != JointStereo) and (modeExtension != 0):
        return None

    copyrightBit = (header[3] & 0x08) == 0x08 #版权 (1 bit)
    originalBit = (header[3] & 0x04) == 0x04 #原版标志 (1 bit)
    emphasis = (header[3] & 0x03) #强调标识 (2 bits)
    if emphasis == 2:
        return None
    
    #帧大小即每帧的采样数，表示一帧数据中采样的个数
    sampleCount = sampleCountTable[mpegVer][layer]
    
    #Layer1帧长调节为4字节，其他两层为1字节
    padding = (4 if (layer == MPEGLayerI) else 1) if paddingBit else 0

    #计算帧长度，下面这段注释是go-lang版本mp3cat<https://github.com/dmulholl/mp3cat>的作者原话
    # Calculate the frame length in bytes. There's a lot of confusion online
    # about how to do this and definitive documentation is hard to find as
    # the official MP3 specification is not publicly available. The
    # basic formula seems to boil down to:
    #
    #     bytes_per_sample = (bit_rate / sampling_rate) / 8
    #     frame_length = sample_count * bytes_per_sample + padding
    #
    # In practice we need to rearrange this formula to avoid rounding errors.
    #
    # I can't find any definitive statement on whether this length is
    # supposed to include the 4-byte header and the optional 2-byte CRC.
    # Experimentation on mp3 files captured from the wild indicates that it
    # includes the header at least.
    frameLength = int((sampleCount / 8) * bitRate / samplingRate + padding)
    return {'type': 'FRAME', 'len': frameLength, 'bitRate': bitRate, 'samplingRate': samplingRate,
        'sampleCount': sampleCount, 'mpegVer': mpegVer, 'layer': layer, 'channelMode': channelMode}

#创建一个新的VBR帧
def NewXingHeader(totalFrames, totalBytes):
    data = bytearray(209)
    data[0] = 0xFF #前面几个数值是合法的，但是是随便从一个mp3文件里面提取的
    data[1] = 0xFB
    data[2] = 0x52
    data[3] = 0xC0

    frame = ParseMusicHeader(data)
    offset = GetSideInfoSize(frame)
    data[offset : offset + 4] = b'Xing'
    data[offset + 7] = 3 #只是总帧数和总字节数有效

    # 将 totalFrames 和 totalBytes 以32位大端字节顺序写入
    struct.pack_into('>I', data, offset + 8, totalFrames)
    struct.pack_into('>I', data, offset + 12, totalBytes)
    return bytes(data)

#在MP3前面添加一个VBR头
#output: 要添加的流对象或文件名
#totalFrames/totalBytes: 总帧数和总字节数
def AddXingHeader(output, totalFrames, totalBytes):
    xingHeader = NewXingHeader(totalFrames, totalBytes)
    if isinstance(output, str):
        tempFile = output + '.mp3cat.tmp'
        with open(output, "rb") as old, open(tempFile, "wb") as new:
            new.write(xingHeader)
            new.write(old.read())
        try:
            os.remove(output)
            os.rename(tempFile, output)
        except Exception as e:
            print(f'Error: {e}')
    else:
        tempStream = io.BytesIO(output.getvalue())
        output.seek(0)
        output.write(xingHeader)
        output.write(tempStream.getvalue())

#从input_里面将ID3V2标签拷贝到目标文件
def AddID3v2Tag(output, input_):
    tag = FindID3v2Tag(input_)
    if not tag:
        return

    if isinstance(output, str):
        tempFile = output + '.mp3cat.tmp'
        with open(output, "rb") as old, open(tempFile, "wb") as new:
            new.write(tag['raw'])
            new.write(old.read())
        try:
            os.remove(output)
            os.rename(tempFile, output)
        except Exception as e:
            print(f'Error: {e}')
    else:
        tempStream = io.BytesIO(output.getvalue())
        output.seek(0)
        output.write(tag['raw'])
        output.write(tempStream.getvalue())

#合并mp3文件
#output: 输出文件名或流对象
#inputs: 输入文件名列表或二进制内容类别
#tagIndex: 是否需要将第n个文件的ID3拷贝过来
#force: 是否覆盖目标文件
#quiet: 是否打印过程
def merge(output: str, inputs: list, tagIndex: int=None, force: bool=True, quiet: bool=False):
    if not force and isinstance(output, str) and os.path.exists(output):
        print(f"Error: the file '{output}' already exists.")
        return
    if inputs and isinstance(inputs[0], str) and output in inputs:
        print(f'Error: the list of input files includes the output file.')
        return

    printInfo = (lambda x: x) if quiet else (lambda x: print(x))

    outputStream = open(output, 'wb') if isinstance(output, str) else output
    
    totalFrames = 0
    totalBytes = 0
    totalFiles = 0
    firstBitRate = 0
    isVBR = False
    for idx, input_ in enumerate(inputs):
        needClose = False
        if isinstance(input_, str):
            printInfo(f' + {input_}')
            input_ = open(input_, 'rb')
            needClose = True
        else:
            printInfo(f' + <stream {idx}>')

        isFirstFrame = True
        for frame in IterFrame(input_):
            if isFirstFrame: #第一个帧如果是VBR，不包含音乐数据
                isFirstFrame = False
                if IsVBRHeader(frame):
                    continue

            if firstBitRate == 0:
                firstBitRate = frame['bitRate']
            elif frame['bitRate'] != firstBitRate:
                isVBR = True
            
            outputStream.write(frame['raw'])
            totalFrames += 1
            totalBytes += frame['len']
        totalFiles += 1
        if needClose:
            input_.close()

    if isinstance(output, str):
        outputStream.close()

    #如果不同的文件的比特率不同，则在前面添加一个VBR头
    if isVBR:
        printInfo("• Multiple bitrates detected. Adding VBR header.")
        AddXingHeader(output, totalFrames, totalBytes)
        if isinstance(output, str):
            try:
                tempStream.close()
                os.remove(output + '.mp3cat.tmp')
            except:
                pass

    if tagIndex is not None and tagIndex < len(inputs):
        input_ = inputs[tagIndex]
        needClose = False
        if isinstance(input_, str):
            printInfo(f"• Copying ID3 tag from: {input_}")
            input_ = open(input_, 'rb')
            needClose = True
        else:
            printInfo(f'• Copying ID3 tag from: <stream {tagIndex}>')
        AddID3v2Tag(output, input_)
        if needClose:
            input_.close()

    printInfo(f"• {totalFiles} files merged.")
