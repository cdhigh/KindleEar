#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#Azure text-to-speech
#https://learn.microsoft.com/en-us/azure/ai-services/speech-service/rest-text-to-speech
import json
from urllib.parse import urljoin
from urlopener import UrlOpener
from .tts_base import TTSBase

#键为BCP-47语种代码，值为语音名字列表
azuretts_languages = {
    'af-ZA': ['af-ZA-AdriNeural', 'af-ZA-WillemNeural'],
    'am-ET': ['am-ET-MekdesNeural', 'am-ET-AmehaNeural'],
    'ar-AE': ['ar-AE-FatimaNeural', 'ar-AE-HamdanNeural'],
    'ar-BH': ['ar-BH-LailaNeural', 'ar-BH-AliNeural'],
    'ar-DZ': ['ar-DZ-AminaNeural', 'ar-DZ-IsmaelNeural'],
    'ar-EG': ['ar-EG-SalmaNeural', 'ar-EG-ShakirNeural'],
    'ar-IQ': ['ar-IQ-RanaNeural', 'ar-IQ-BasselNeural'],
    'ar-JO': ['ar-JO-SanaNeural', 'ar-JO-TaimNeural'],
    'ar-KW': ['ar-KW-NouraNeural', 'ar-KW-FahedNeural'],
    'ar-LB': ['ar-LB-LaylaNeural', 'ar-LB-RamiNeural'],
    'ar-LY': ['ar-LY-ImanNeural', 'ar-LY-OmarNeural'],
    'ar-MA': ['ar-MA-MounaNeural', 'ar-MA-JamalNeural'],
    'ar-OM': ['ar-OM-AyshaNeural', 'ar-OM-AbdullahNeural'],
    'ar-QA': ['ar-QA-AmalNeural', 'ar-QA-MoazNeural'],
    'ar-SA': ['ar-SA-ZariyahNeural', 'ar-SA-HamedNeural'],
    'ar-SY': ['ar-SY-AmanyNeural', 'ar-SY-LaithNeural'],
    'ar-TN': ['ar-TN-ReemNeural', 'ar-TN-HediNeural'],
    'ar-YE': ['ar-YE-MaryamNeural', 'ar-YE-SalehNeural'],
    'az-AZ': ['az-AZ-BanuNeural', 'az-AZ-BabekNeural'],
    'bg-BG': ['bg-BG-KalinaNeural', 'bg-BG-BorislavNeural'],
    'bn-BD': ['bn-BD-NabanitaNeural', 'bn-BD-PradeepNeural'],
    'bn-IN': ['bn-IN-TanishaaNeural', 'bn-IN-BashkarNeural'],
    'bs-BA': ['bs-BA-VesnaNeural', 'bs-BA-GoranNeural'],
    'ca-ES': ['ca-ES-JoanaNeural', 'ca-ES-EnricNeural', 'ca-ES-AlbaNeural'],
    'cs-CZ': ['cs-CZ-VlastaNeural', 'cs-CZ-AntoninNeural'],
    'cy-GB': ['cy-GB-NiaNeural', 'cy-GB-AledNeural'],
    'da-DK': ['da-DK-ChristelNeural', 'da-DK-JeppeNeural'],
    'de-AT': ['de-AT-IngridNeural', 'de-AT-JonasNeural'],
    'de-CH': ['de-CH-LeniNeural', 'de-CH-JanNeural'],
    'de-DE': ['de-DE-KatjaNeural', 'de-DE-ConradNeural', 'de-DE-AmalaNeural', 'de-DE-BerndNeural', 'de-DE-ChristophNeural', 'de-DE-ElkeNeural', 'de-DE-FlorianMultilingualNeural', 'de-DE-GiselaNeural', 'de-DE-KasperNeural', 'de-DE-KillianNeural', 'de-DE-KlarissaNeural', 'de-DE-KlausNeural', 'de-DE-LouisaNeural', 'de-DE-MajaNeural', 'de-DE-RalfNeural', 'de-DE-SeraphinaMultilingualNeural', 'de-DE-TanjaNeural'],
    'el-GR': ['el-GR-AthinaNeural', 'el-GR-NestorasNeural'],
    'en-AU': ['en-AU-NatashaNeural', 'en-AU-WilliamNeural', 'en-AU-AnnetteNeural', 'en-AU-CarlyNeural', 'en-AU-DarrenNeural', 'en-AU-DuncanNeural', 'en-AU-ElsieNeural', 'en-AU-FreyaNeural', 'en-AU-JoanneNeural', 'en-AU-KenNeural', 'en-AU-KimNeural', 'en-AU-NeilNeural', 'en-AU-TimNeural', 'en-AU-TinaNeural'],
    'en-CA': ['en-CA-ClaraNeural', 'en-CA-LiamNeural'],
    'en-GB': ['en-GB-SoniaNeural', 'en-GB-RyanNeural', 'en-GB-LibbyNeural', 'en-GB-AbbiNeural', 'en-GB-AlfieNeural', 'en-GB-BellaNeural', 'en-GB-ElliotNeural', 'en-GB-EthanNeural', 'en-GB-HollieNeural', 'en-GB-MaisieNeural', 'en-GB-NoahNeural', 'en-GB-OliverNeural', 'en-GB-OliviaNeural', 'en-GB-ThomasNeural', 'en-GB-MiaNeural'],
    'en-HK': ['en-HK-YanNeural', 'en-HK-SamNeural'],
    'en-IE': ['en-IE-EmilyNeural', 'en-IE-ConnorNeural'],
    'en-IN': ['en-IN-NeerjaNeural', 'en-IN-PrabhatNeural'],
    'en-KE': ['en-KE-AsiliaNeural', 'en-KE-ChilembaNeural'],
    'en-NG': ['en-NG-EzinneNeural', 'en-NG-AbeoNeural'],
    'en-NZ': ['en-NZ-MollyNeural', 'en-NZ-MitchellNeural'],
    'en-PH': ['en-PH-RosaNeural', 'en-PH-JamesNeural'],
    'en-SG': ['en-SG-LunaNeural', 'en-SG-WayneNeural'],
    'en-TZ': ['en-TZ-ImaniNeural', 'en-TZ-ElimuNeural'],
    'en-US': ['en-US-AvaMultilingualNeural', 'en-US-AndrewMultilingualNeural', 'en-US-EmmaMultilingualNeural', 'en-US-BrianMultilingualNeural', 'en-US-AvaNeural', 'en-US-AndrewNeural', 'en-US-EmmaNeural', 'en-US-BrianNeural', 'en-US-JennyNeural', 'en-US-GuyNeural', 'en-US-AriaNeural', 'en-US-DavisNeural', 'en-US-JaneNeural', 'en-US-JasonNeural', 'en-US-SaraNeural', 'en-US-TonyNeural', 'en-US-NancyNeural', 'en-US-AmberNeural', 'en-US-AnaNeural', 'en-US-AshleyNeural', 'en-US-BrandonNeural', 'en-US-ChristopherNeural', 'en-US-CoraNeural', 'en-US-ElizabethNeural', 'en-US-EricNeural', 'en-US-JacobNeural', 'en-US-JennyMultilingualNeural', 'en-US-MichelleNeural', 'en-US-MonicaNeural', 'en-US-RogerNeural', 'en-US-RyanMultilingualNeural', 'en-US-SteffanNeural'],
    'en-ZA': ['en-ZA-LeahNeural', 'en-ZA-LukeNeural'],
    'es-AR': ['es-AR-ElenaNeural', 'es-AR-TomasNeural'],
    'es-BO': ['es-BO-SofiaNeural', 'es-BO-MarceloNeural'],
    'es-CL': ['es-CL-CatalinaNeural', 'es-CL-LorenzoNeural'],
    'es-CO': ['es-CO-SalomeNeural', 'es-CO-GonzaloNeural'],
    'es-CR': ['es-CR-MariaNeural', 'es-CR-JuanNeural'],
    'es-CU': ['es-CU-BelkysNeural', 'es-CU-ManuelNeural'],
    'es-DO': ['es-DO-RamonaNeural', 'es-DO-EmilioNeural'],
    'es-EC': ['es-EC-AndreaNeural', 'es-EC-LuisNeural'],
    'es-ES': ['es-ES-ElviraNeural', 'es-ES-AlvaroNeural', 'es-ES-AbrilNeural', 'es-ES-ArnauNeural', 'es-ES-DarioNeural', 'es-ES-EliasNeural', 'es-ES-EstrellaNeural', 'es-ES-IreneNeural', 'es-ES-LaiaNeural', 'es-ES-LiaNeural', 'es-ES-NilNeural', 'es-ES-SaulNeural', 'es-ES-TeoNeural', 'es-ES-TrianaNeural', 'es-ES-VeraNeural', 'es-ES-XimenaNeural'],
    'es-GQ': ['es-GQ-TeresaNeural', 'es-GQ-JavierNeural'],
    'es-GT': ['es-GT-MartaNeural', 'es-GT-AndresNeural'],
    'es-HN': ['es-HN-KarlaNeural', 'es-HN-CarlosNeural'],
    'es-MX': ['es-MX-DaliaNeural', 'es-MX-JorgeNeural', 'es-MX-BeatrizNeural', 'es-MX-CandelaNeural', 'es-MX-CarlotaNeural', 'es-MX-CecilioNeural', 'es-MX-GerardoNeural', 'es-MX-LarissaNeural', 'es-MX-LibertoNeural', 'es-MX-LucianoNeural', 'es-MX-MarinaNeural', 'es-MX-NuriaNeural', 'es-MX-PelayoNeural', 'es-MX-RenataNeural', 'es-MX-YagoNeural'],
    'es-NI': ['es-NI-YolandaNeural', 'es-NI-FedericoNeural'],
    'es-PA': ['es-PA-MargaritaNeural', 'es-PA-RobertoNeural'],
    'es-PE': ['es-PE-CamilaNeural', 'es-PE-AlexNeural'],
    'es-PR': ['es-PR-KarinaNeural', 'es-PR-VictorNeural'],
    'es-PY': ['es-PY-TaniaNeural', 'es-PY-MarioNeural'],
    'es-SV': ['es-SV-LorenaNeural', 'es-SV-RodrigoNeural'],
    'es-US': ['es-US-PalomaNeural', 'es-US-AlonsoNeural'],
    'es-UY': ['es-UY-ValentinaNeural', 'es-UY-MateoNeural'],
    'es-VE': ['es-VE-PaolaNeural', 'es-VE-SebastianNeural'],
    'et-EE': ['et-EE-AnuNeural', 'et-EE-KertNeural'],
    'eu-ES': ['eu-ES-AinhoaNeural', 'eu-ES-AnderNeural'],
    'fa-IR': ['fa-IR-DilaraNeural', 'fa-IR-FaridNeural'],
    'fi-FI': ['fi-FI-SelmaNeural', 'fi-FI-HarriNeural', 'fi-FI-NooraNeural'],
    'fil-PH': ['fil-PH-BlessicaNeural', 'fil-PH-AngeloNeural'],
    'fr-BE': ['fr-BE-CharlineNeural', 'fr-BE-GerardNeural'],
    'fr-CA': ['fr-CA-SylvieNeural', 'fr-CA-JeanNeural', 'fr-CA-AntoineNeural', 'fr-CA-ThierryNeural'],
    'fr-CH': ['fr-CH-ArianeNeural', 'fr-CH-FabriceNeural'],
    'fr-FR': ['fr-FR-DeniseNeural', 'fr-FR-HenriNeural', 'fr-FR-AlainNeural', 'fr-FR-BrigitteNeural', 'fr-FR-CelesteNeural', 'fr-FR-ClaudeNeural', 'fr-FR-CoralieNeural', 'fr-FR-EloiseNeural', 'fr-FR-JacquelineNeural', 'fr-FR-JeromeNeural', 'fr-FR-JosephineNeural', 'fr-FR-MauriceNeural', 'fr-FR-RemyMultilingualNeural', 'fr-FR-VivienneMultilingualNeural', 'fr-FR-YvesNeural', 'fr-FR-YvetteNeural'],
    'ga-IE': ['ga-IE-OrlaNeural', 'ga-IE-ColmNeural'],
    'gl-ES': ['gl-ES-SabelaNeural', 'gl-ES-RoiNeural'],
    'gu-IN': ['gu-IN-DhwaniNeural', 'gu-IN-NiranjanNeural'],
    'he-IL': ['he-IL-HilaNeural', 'he-IL-AvriNeural'],
    'hi-IN': ['hi-IN-SwaraNeural', 'hi-IN-MadhurNeural'],
    'hr-HR': ['hr-HR-GabrijelaNeural', 'hr-HR-SreckoNeural'],
    'hu-HU': ['hu-HU-NoemiNeural', 'hu-HU-TamasNeural'],
    'hy-AM': ['hy-AM-AnahitNeural', 'hy-AM-HaykNeural'],
    'id-ID': ['id-ID-GadisNeural', 'id-ID-ArdiNeural'],
    'is-IS': ['is-IS-GudrunNeural', 'is-IS-GunnarNeural'],
    'it-IT': ['it-IT-ElsaNeural', 'it-IT-IsabellaNeural', 'it-IT-DiegoNeural', 'it-IT-BenignoNeural', 'it-IT-CalimeroNeural', 'it-IT-CataldoNeural', 'it-IT-FabiolaNeural', 'it-IT-FiammaNeural', 'it-IT-GianniNeural', 'it-IT-GiuseppeNeural', 'it-IT-ImeldaNeural', 'it-IT-IrmaNeural', 'it-IT-LisandroNeural', 'it-IT-PalmiraNeural', 'it-IT-PierinaNeural', 'it-IT-RinaldoNeural'],
    'ja-JP': ['ja-JP-NanamiNeural', 'ja-JP-KeitaNeural', 'ja-JP-AoiNeural', 'ja-JP-DaichiNeural', 'ja-JP-MayuNeural', 'ja-JP-NaokiNeural', 'ja-JP-ShioriNeural'],
    'jv-ID': ['jv-ID-SitiNeural', 'jv-ID-DimasNeural'],
    'ka-GE': ['ka-GE-EkaNeural', 'ka-GE-GiorgiNeural'],
    'kk-KZ': ['kk-KZ-AigulNeural', 'kk-KZ-DauletNeural'],
    'km-KH': ['km-KH-SreymomNeural', 'km-KH-PisethNeural'],
    'kn-IN': ['kn-IN-SapnaNeural', 'kn-IN-GaganNeural'],
    'ko-KR': ['ko-KR-SunHiNeural', 'ko-KR-InJoonNeural', 'ko-KR-BongJinNeural', 'ko-KR-GookMinNeural', 'ko-KR-HyunsuNeural', 'ko-KR-JiMinNeural', 'ko-KR-SeoHyeonNeural', 'ko-KR-SoonBokNeural', 'ko-KR-YuJinNeural'],
    'lo-LA': ['lo-LA-KeomanyNeural', 'lo-LA-ChanthavongNeural'],
    'lt-LT': ['lt-LT-OnaNeural', 'lt-LT-LeonasNeural'],
    'lv-LV': ['lv-LV-EveritaNeural', 'lv-LV-NilsNeural'],
    'mk-MK': ['mk-MK-MarijaNeural', 'mk-MK-AleksandarNeural'],
    'ml-IN': ['ml-IN-SobhanaNeural', 'ml-IN-MidhunNeural'],
    'mn-MN': ['mn-MN-YesuiNeural', 'mn-MN-BataaNeural'],
    'mr-IN': ['mr-IN-AarohiNeural', 'mr-IN-ManoharNeural'],
    'ms-MY': ['ms-MY-YasminNeural', 'ms-MY-OsmanNeural'],
    'mt-MT': ['mt-MT-GraceNeural', 'mt-MT-JosephNeural'],
    'my-MM': ['my-MM-NilarNeural', 'my-MM-ThihaNeural'],
    'nb-NO': ['nb-NO-PernilleNeural', 'nb-NO-FinnNeural', 'nb-NO-IselinNeural'],
    'ne-NP': ['ne-NP-HemkalaNeural', 'ne-NP-SagarNeural'],
    'nl-BE': ['nl-BE-DenaNeural', 'nl-BE-ArnaudNeural'],
    'nl-NL': ['nl-NL-FennaNeural', 'nl-NL-MaartenNeural', 'nl-NL-ColetteNeural'],
    'pl-PL': ['pl-PL-AgnieszkaNeural', 'pl-PL-MarekNeural', 'pl-PL-ZofiaNeural'],
    'ps-AF': ['ps-AF-LatifaNeural', 'ps-AF-GulNawazNeural'],
    'pt-BR': ['pt-BR-FranciscaNeural', 'pt-BR-AntonioNeural', 'pt-BR-BrendaNeural', 'pt-BR-DonatoNeural', 'pt-BR-ElzaNeural', 'pt-BR-FabioNeural', 'pt-BR-GiovannaNeural', 'pt-BR-HumbertoNeural', 'pt-BR-JulioNeural', 'pt-BR-LeilaNeural', 'pt-BR-LeticiaNeural', 'pt-BR-ManuelaNeural', 'pt-BR-NicolauNeural', 'pt-BR-ThalitaNeural', 'pt-BR-ValerioNeural', 'pt-BR-YaraNeural'],
    'pt-PT': ['pt-PT-RaquelNeural', 'pt-PT-DuarteNeural', 'pt-PT-FernandaNeural'],
    'ro-RO': ['ro-RO-AlinaNeural', 'ro-RO-EmilNeural'],
    'ru-RU': ['ru-RU-SvetlanaNeural', 'ru-RU-DmitryNeural', 'ru-RU-DariyaNeural'],
    'si-LK': ['si-LK-ThiliniNeural', 'si-LK-SameeraNeural'],
    'sk-SK': ['sk-SK-ViktoriaNeural', 'sk-SK-LukasNeural'],
    'sl-SI': ['sl-SI-PetraNeural', 'sl-SI-RokNeural'],
    'so-SO': ['so-SO-UbaxNeural', 'so-SO-MuuseNeural'],
    'sq-AL': ['sq-AL-AnilaNeural', 'sq-AL-IlirNeural'],
    'sr-Latn-RS': ['sr-Latn-RS-NicholasNeural', 'sr-Latn-RS-SophieNeural'],
    'sr-RS': ['sr-RS-SophieNeural', 'sr-RS-NicholasNeural'],
    'su-ID': ['su-ID-TutiNeural', 'su-ID-JajangNeural'],
    'sv-SE': ['sv-SE-SofieNeural', 'sv-SE-MattiasNeural', 'sv-SE-HilleviNeural'],
    'sw-KE': ['sw-KE-ZuriNeural', 'sw-KE-RafikiNeural'],
    'sw-TZ': ['sw-TZ-RehemaNeural', 'sw-TZ-DaudiNeural'],
    'ta-IN': ['ta-IN-PallaviNeural', 'ta-IN-ValluvarNeural'],
    'ta-LK': ['ta-LK-SaranyaNeural', 'ta-LK-KumarNeural'],
    'ta-MY': ['ta-MY-KaniNeural', 'ta-MY-SuryaNeural'],
    'ta-SG': ['ta-SG-VenbaNeural', 'ta-SG-AnbuNeural'],
    'te-IN': ['te-IN-ShrutiNeural', 'te-IN-MohanNeural'],
    'th-TH': ['th-TH-PremwadeeNeural', 'th-TH-NiwatNeural', 'th-TH-AcharaNeural'],
    'tr-TR': ['tr-TR-EmelNeural', 'tr-TR-AhmetNeural'],
    'uk-UA': ['uk-UA-PolinaNeural', 'uk-UA-OstapNeural'],
    'ur-IN': ['ur-IN-GulNeural', 'ur-IN-SalmanNeural'],
    'ur-PK': ['ur-PK-UzmaNeural', 'ur-PK-AsadNeural'],
    'uz-UZ': ['uz-UZ-MadinaNeural', 'uz-UZ-SardorNeural'],
    'vi-VN': ['vi-VN-HoaiMyNeural', 'vi-VN-NamMinhNeural'],
    'wuu-CN': ['wuu-CN-XiaotongNeural', 'wuu-CN-YunzheNeural'],
    'yue-CN': ['yue-CN-XiaoMinNeural', 'yue-CN-YunSongNeural'],
    'zh-CN': ['zh-CN-XiaoxiaoNeural', 'zh-CN-YunxiNeural', 'zh-CN-YunjianNeural', 'zh-CN-XiaoyiNeural', 'zh-CN-YunyangNeural', 'zh-CN-XiaochenNeural', 'zh-CN-XiaohanNeural', 'zh-CN-XiaomengNeural', 'zh-CN-XiaomoNeural', 'zh-CN-XiaoqiuNeural', 'zh-CN-XiaoruiNeural', 'zh-CN-XiaoshuangNeural', 'zh-CN-XiaoxiaoMultilingualNeural', 'zh-CN-XiaoyanNeural', 'zh-CN-XiaoyouNeural', 'zh-CN-XiaozhenNeural', 'zh-CN-YunfengNeural', 'zh-CN-YunhaoNeural', 'zh-CN-YunxiaNeural', 'zh-CN-YunyeNeural', 'zh-CN-YunzeNeural', 'zh-CN-XiaoxuanNeural'],
    'zh-CN-henan': ['zh-CN-henan-YundengNeural'],
    'zh-CN-liaoning': ['zh-CN-liaoning-XiaobeiNeural'],
    'zh-CN-shaanxi': ['zh-CN-shaanxi-XiaoniNeural'],
    'zh-CN-shandong': ['zh-CN-shandong-YunxiangNeural'],
    'zh-CN-sichuan': ['zh-CN-sichuan-YunxiNeural'],
    'zh-HK': ['zh-HK-HiuMaanNeural', 'zh-HK-WanLungNeural', 'zh-HK-HiuGaaiNeural'],
    'zh-TW': ['zh-TW-HsiaoChenNeural', 'zh-TW-YunJheNeural', 'zh-TW-HsiaoYuNeural'],
    'zu-ZA': ['zu-ZA-ThandoNeural', 'zu-ZA-ThembaNeural'],
}

#区域字典，键为区域代码，值为显示字符串
azure_regions = {
    'southafricanorth': 'South Africa North',
    'eastasia': 'East Asia',
    'southeastasia': 'Southeast Asia',
    'australiaeast': 'Australia East',
    'centralindia': 'Central India',
    'japaneast': 'Japan East',
    'japanwest': 'Japan West',
    'koreacentral': 'Korea Central',
    'canadacentral': 'Canada Central',
    'northeurope': 'North Europe',
    'westeurope': 'West Europe',
    'francecentral': 'France Central',
    'germanywestcentral': 'Germany West Central',
    'norwayeast': 'Norway East',
    'swedencentral': 'Sweden Central',
    'switzerlandnorth': 'Switzerland North',
    'switzerlandwest': 'Switzerland West',
    'uksouth': 'UK South',
    'uaenorth': 'UAE North',
    'brazilsouth': 'Brazil South',
    'qatarcentral': 'Qatar Central',
    'centralus': 'Central US',
    'eastus': 'East US',
    'eastus2': 'East US 2',
    'northcentralus': 'North Central US',
    'southcentralus': 'South Central US',
    'westcentralus': 'West Central US',
    'westus': 'West US',
    'westus2': 'West US 2',
    'westus3': 'West US 3',
}

class AzureTTS(TTSBase):
    name = 'AzureTTS'
    alias = 'Microsoft Azure Text to Speech'
    need_api_key = True
    api_key_hint = 'subscription key'
    default_api_host = 'https://{region}.tts.speech.microsoft.com/cognitiveservices/'
    default_api_host2 = 'https://{region}.tts.speech.azure.us/cognitiveservices/'
    default_timeout = 60
    #https://learn.microsoft.com/en-us/azure/ai-services/speech-service/speech-services-quotas-and-limits
    request_interval = 3  #20 transactions per 60 seconds
    #每段音频不能超过10分钟，所以对于中文，大约2000字，因为大约1500 word
    max_len_per_request = 1000
    languages = azuretts_languages
    regions = azure_regions
    region_url = 'https://learn.microsoft.com/en-us/azure/ai-services/speech-service/regions'
    voice_url = 'https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts'
    language_url = 'https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts'
    
    def __init__(self, params):
        super().__init__(params)
        if self.region in ('usgovarizona', 'usgovvirginia'):
            self.mainUrl = self.default_api_host2.format(region=self.region)
        else:
            self.mainUrl = self.default_api_host.format(region=self.region)
        if not self.mainUrl.endswith('/'):
            self.mainUrl += '/'
        self.opener = UrlOpener(timeout=self.timeout, headers={'Ocp-Apim-Subscription-Key': self.key})

    #获取支持的语音列表，注意，这个会返回一个超级大的json对象
    #或者可以直接到网页去查询
    #https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts
    def voice_list(self):
        url = urljoin(self.mainUrl, 'voices/list')
        resp = self.opener.open(url)
        if resp.status_code == 200:
            return resp.json()
        else:
            return {'status': UrlOpener.CodeMap(resp.status_code)}

    #文本转换为语音，
    #支持的音频格式参考： 
    #<https://learn.microsoft.com/en-us/azure/ai-services/speech-service/rest-text-to-speech?tabs=streaming#audio-outputs>
    def tts(self, text):
        url = urljoin(self.mainUrl, 'v1')
        headers = {'Content-Type': 'application/ssml+xml',
            'X-Microsoft-OutputFormat': 'audio-24khz-48kbitrate-mono-mp3',
            'User-Agent': 'KindleEar',
        }
        resp = self.opener.open(url, headers=headers, data=self.ssml(text))
        if resp.status_code == 200:
            #返回的是stream流形式
            content = b''.join(line for line in resp.iter_content(chunk_size=None))
            return ('audio/mpeg', content)
        else:
            raise Exception(self.opener.CodeMap(resp.status_code))



