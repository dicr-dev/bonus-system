import {api} from './api'

export interface TrainingCriterion {id:string; title:string; weight:number}
export interface TrainingRubric {id:string; title:string; criteria:TrainingCriterion[]; created_at:string}
export interface ExtractionInfo {
 speakers:string[]; has_timecodes:boolean; summary_excluded:boolean;
 last_timecode:string|null; characters:number; warnings:string[]
}
export interface Training {
 id:string; deal_id:string; deal_title:string; deal_bitrix_id:number; trainer_id:string;
 trainer_name:string; training_date:string; module:string; training_number:number; speaker_label:string;
 filename:string; sha256:string; extraction_info:ExtractionInfo; created_at:string
}
export interface TrainingAssessment {
 training_id:string; rubric_id:string;
 criteria:{id:string; score:number|string|null; explanation:string; evidence:{quote:string; timecode:string}[]}[];
 strengths:string; recommendations:string; limitations:string
}
export interface TrainingReview {
 id:string; training_id:string; rubric_id:string; assessment:TrainingAssessment;
 total:number|string|null; status:string; created_at:string; confirmed_at:string|null
}
export interface TrainingDetails extends Training {transcript:string; reviews:TrainingReview[]}
export interface TrainingOptions {
 trainers:{id:string; full_name:string; is_active:boolean}[]; rubrics:TrainingRubric[]; max_file_bytes:number
}
export interface TrainingFilters {deal_id?:string; trainer_id?:string; date_from?:string; date_to?:string; offset?:number; limit?:number}
export async function trainingOptions():Promise<TrainingOptions>{return (await api.get('/training/options')).data}
export async function searchTrainingDeals(q:string):Promise<{id:string; bitrix_id:number; title:string; module_name:string|null}[]>{return (await api.get('/training/deals',{params:{q}})).data}
export async function trainingSessions(params:TrainingFilters):Promise<{items:Training[]; total:number}>{return (await api.get('/training/sessions',{params})).data}
export async function trainingDetails(id:string):Promise<TrainingDetails>{return (await api.get(`/training/sessions/${id}`)).data}
export async function inspectTraining(file:File):Promise<ExtractionInfo>{const data=new FormData();data.append('file',file);return (await api.post('/training/inspect',data)).data}
export async function uploadTraining(file:File,metadata:unknown):Promise<Training>{const data=new FormData();data.append('file',file);data.append('metadata',JSON.stringify(metadata));return (await api.post('/training/sessions',data)).data}
export async function saveTrainingReview(id:string,data:TrainingAssessment):Promise<TrainingReview>{return (await api.post(`/training/sessions/${id}/reviews`,data)).data}
export async function confirmTrainingReview(id:string,reviewId:string):Promise<TrainingReview>{return (await api.post(`/training/sessions/${id}/reviews/${reviewId}/confirm`)).data}
export async function createTrainingRubric(data:{title:string; criteria:TrainingCriterion[]}):Promise<TrainingRubric>{return (await api.post('/training/rubrics',data)).data}
export interface TrainingRatingRow {trainer_id:string; trainer_name:string; module:string; training_number:number; count:number; unscored:number; average:number|string|null}
export async function trainingRating(params:{rubric_id:string; date_from?:string; date_to?:string}):Promise<{rubric:TrainingRubric; items:TrainingRatingRow[]}>{return (await api.get('/training/rating',{params})).data}
export function trainingPromptUrl(id:string,rubricId:string){return `/api/v1/training/sessions/${id}/prompt?rubric_id=${encodeURIComponent(rubricId)}`}
export function trainingFileUrl(id:string){return `/api/v1/training/sessions/${id}/file`}

export function parseTrainingAssessment(text:string):TrainingAssessment {
 const trimmed=text.trim().replace(/^```(?:json)?\s*/i,'').replace(/\s*```$/,'')
 const data=JSON.parse(trimmed)
 if(!data||typeof data!=='object'||!Array.isArray(data.criteria))throw new Error('Нужен JSON с массивом criteria')
 return data as TrainingAssessment
}
