//// Neoffice — this import of the translator is ours (maintenance#1490, formatBytes).
import _ from './translate'

/**
 * Function to return extension of a file
 * @param filename name of the file with extension
 * @returns extension
 */
export const getFileExtension = (filename: string) => {

    const fileNameWithoutQuery = filename?.split('?')[0]

    const extension = fileNameWithoutQuery?.split('.').pop()?.toLocaleLowerCase() ?? ''
    return extension;
}

/**
 * Function to format bytes to human readable format
 * @param bytes size in bytes
 * @param decimals number of decimal places
 * @returns string of human readable size
 */
export const formatBytes = (bytes: number, decimals = 2) => {

    //// Neoffice — the units go through the catalogue and the number takes the user's decimal sign
    //// (maintenance#1490): upstream wrote « 12.5 Bytes » on the dropped file, in English, in a French screen.
    const sizes = [_('Bytes'), _('KB'), _('MB'), _('GB'), _('TB'), 'PB', 'EB', 'ZB', 'YB']
    if (bytes === 0) return '0 ' + sizes[0]

    const k = 1024
    //// Neoffice — upstream's list of units stood here, untranslated: it moved above, through _() (maintenance#1490).

    const i = Math.floor(Math.log(bytes) / Math.log(k))

    //// Neoffice — the number in the user's decimal sign (« 12,5 Ko »), upstream joined it raw (maintenance#1490).
    const value = parseFloat((bytes / Math.pow(k, i)).toFixed(decimals))
    return value.toLocaleString(window?.frappe?.boot?.lang || undefined) + ' ' + sizes[i]
}


export const imageExt = ["jpeg", "jpg", "png"]

export const excelExt = ['csv', 'xls', 'xlsx']

export const pptExt = ['ppt', 'pptx']

export const wordExt = ['doc', 'docx']

export const videoExt = ['mp4', 'mkv', 'webm', 'avi', 'mov']

export const audioExt = ['mp3', 'wav', 'ogg', 'flac']

export const getFileType = (ext: string) => {
    switch (ext) {
        case 'pdf': return 'pdf'
        case 'doc': return 'word'
        case 'docx': return 'word'
        case 'xls': return 'excel'
        case 'xlsx': return 'excel'
        case 'ppt': return 'powerpoint'
        case 'pptx': return 'powerpoint'
        case 'mp3': return 'audio'
        case 'wav': return 'audio'
        case 'ogg': return 'audio'
        case 'flac': return 'audio'
        case 'mp4': return 'video'
        case 'mkv': return 'video'
        case 'webm': return 'video'
        case 'avi': return 'video'
        case 'mov': return 'video'
        case 'jpeg': return 'image'
        case 'jpg': return 'image'
        case 'png': return 'image'
        default: return 'file'
    }
}