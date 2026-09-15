"""Extract only the printed CCCD identifier; do not decode or update QR profiles."""
import re
from .domain import BusinessError


def lookup_key(raw):
    value=str(raw or '').strip()
    if len(value)>8192:raise BusinessError('Chuỗi tìm khách quá dài.')
    if '|' in value:
        fields=value.split('|')
        if len(fields)<7 or not re.fullmatch(r'[0-9]{12}',fields[0].strip()) or not re.fullmatch(r'[0-9]{8}',fields[-1].strip()):
            raise BusinessError('QR CCCD chưa đủ hoặc sai định dạng. Quét lại hoặc nhập số CCCD.')
        return fields[0].strip()
    if len(value)>100:raise BusinessError('Từ khóa tìm khách tối đa 100 ký tự.')
    return value
